import re
import requests
from urllib.parse import urlsplit
from collections import deque
from bs4 import BeautifulSoup
from email_validator import validate_email, EmailNotValidError
import pprint
pp = pprint.PrettyPrinter(indent=4)
from csv import writer
import os
import concurrent.futures
import urllib.request

def validate(emails):
    valid_emails = set()
    for email in emails:
        try:
            valid = validate_email(email)
            email = valid.email
            if email:
                valid_emails.add(email)
        except EmailNotValidError as e:
            pass
    return valid_emails

def email_placeholder(soup, placeholders):
    alls = soup.findAll("input", {'type': 'email'})
    for placeholder in alls:
        val = placeholder.get('placeholder')
        try:
            mtchh = re.search(r"[a-zA-Z0-9\.\-\+\_]+@[a-zA-Z0-9\.\-\+\_]+\.[a-z]{2,5}", val)
            if mtchh:
                placeholders.add(mtchh[0])
        except: pass

def remove_unnecessary_mails(placeholders, emails, domain_name):
    def remove_place_mails(val):
        if val not in placeholders:
            return True

    def remove_other_sec_mails(lst,val):
        try:
            if val not in lst:
                return True
        except: pass
    
    def remove_other_domain_mails(emails, pml, sml, oml, d_n):
        if pml+sml <=2:
            try:
                rnge = oml - (pml+sml)
                emails_temp_other = emails['Others'].copy()
                for ele in emails_temp_other:
                    if rnge == 0:break
                    if d_n not in ele:
                        emails['Others'].remove(ele)
                        rnge -= 1
            except:
                pass
        return emails['Others']

    emails_temp = emails.copy()
    for k,v in emails_temp.items():
        emails[k] = list(filter(remove_place_mails, v))

    for k,v in emails_temp.items():
        if k=='Secondary' or k=='Others':
            if k == 'Secondary':
                emails[k] = list(filter(lambda vals: remove_other_sec_mails(emails['Primary'], vals),emails[k]))
            elif k == 'Others':
                emails[k] = list(filter(lambda vals: remove_other_sec_mails(emails['Primary'] + emails['Secondary'], vals), emails[k]))
    primary_mail_len = len(emails['Primary'])
    secondary_mail_len = len(emails['Secondary'])
    other_mail_len = len(emails['Others'])
    emails['Others'] = remove_other_domain_mails(emails, primary_mail_len, secondary_mail_len, other_mail_len, domain_name)
    return emails

def write_json_to_csv(url_json_arr, upload_dir_path):
    result_xlsx = os.path.join(upload_dir_path, 'result.xlsx')
    print("result path:", result_xlsx)
    all_url_email_lst = []
    for i in range(len(url_json_arr)):
        url_email_lst = []
        url_dct = url_json_arr[i]
        itrr = iter(url_dct)
        key = next(itrr)
        if key=='social_media':
            key = next(itrr)
        url_email_lst.append(key)

        keys = ['Primary', 'Secondary', 'Others']
        cnt = 0
        for k in range(len(url_dct[key])):
            for ele in url_dct[key][keys[k]]:
                url_email_lst.append(ele)
                cnt += 1
                if cnt==3:break
            if cnt==3:break

        if cnt != 3 and len(url_email_lst)<=3:
            while cnt !=3:
                url_email_lst.append('')
                cnt += 1

        if len(url_dct['social_media'])==0:
            url_email_lst.append('')
        else:
            url_email_lst.append(url_dct['social_media'])
        all_url_email_lst.append(url_email_lst)

    print("All list:", url_email_lst)
    with open(result_xlsx, 'w') as f:
        print("File written successfully!")
        print("File path was:", result_xlsx)
        writerobj = writer(f)
        columns = ['domain_name', 'primary_mail', 'secondary_mail', 'other_mail', 'social_media']
        writerobj.writerow(columns)
        for kv in all_url_email_lst:
            writerobj.writerow(kv)
        f.close()
    return result_xlsx

def scraped_url(url, scraped, headers, placeholders, about_emails, contact_emails, other_emails):
    parts1 = urlsplit(url)
    path = '{0.path}'.format(parts1)
    scraped.add(url)
    print(f"Crawling the URL {url}")
    try:
        response = requests.get(url, headers=headers)
        soup1 = BeautifulSoup(response.content, 'lxml')
        email_placeholder(soup1, placeholders)
    except:
        pass
    
    new_emails = set(re.findall(r"[a-zA-Z0-9\.\-\+\_]+@[a-zA-Z0-9\.\-\+\_]+\.[a-z]{2,5}", response.text, re.I))
    if path.startswith('/about') and 'contact' not in path:
        about_emails.update(new_emails)
        about_emails = validate(list(about_emails))

    elif 'contact' in path:
        contact_emails.update(new_emails)
        contact_emails = validate(list(contact_emails))

    else:
        other_emails.update(new_emails)
        other_emails = validate(list(other_emails))

def scraping_emails(list_of_urls, upload_dir_path):
    PREFIX = r'https?://(?:www\.)?'
    SITES = ['twitter.com/', 'youtube.com/',
            '(?:[a-z]{2}\.)?linkedin.com/(?:company/|in/|pub/)',
            'github.com/', '(?:[a-z]{2}-[a-z]{2}\.)?facebook.com/', 'fb.co',
            'plus\.google.com/', 'pinterest.com/','in.pinterest.com/', 'instagram.com/','behance.net/',
            'snapchat.com/', 'flipboard.com/', 'flickr.com',
            'google.com/+', 'weibo.com/', 'periscope.tv/',
            'telegram.me/', 'soundcloud.com', 'feeds.feedburner.com',
            'vimeo.com', 'slideshare.net', 'vkontakte.ru']
    BETWEEN = ['user/', 'add/', 'pages/', '#!/', 'photos/',
            'u/0/']
    ACCOUNT = r'[\w\+_@\.\-/%]+'
    PATTERN = (
        r'%s(?:%s)(?:%s)?%s' %
        (PREFIX, '|'.join(SITES), '|'.join(BETWEEN), ACCOUNT))
    SOCIAL_REX = re.compile(PATTERN, flags=re.I)
    urls = list_of_urls[1:] if list_of_urls[0] == 'websites' else list_of_urls[:]

    url_json_arr = []
    for original_url in urls:
        url_dct = {}
        try:
            unscraped = deque([original_url])  
        except Exception as e: pass

        scraped = set()  
        emails = dict()
        about_emails = set()
        contact_emails = set()
        other_emails = set()
        social_media = set()

        parts = urlsplit(original_url)
        domain_name = '{0.netloc}'.format(parts)
        base_url = '{0.scheme}://{0.netloc}'.format(parts)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:55.0) Gecko/20100101 Firefox/55.0',
        }

        soup = BeautifulSoup(requests.get(original_url, headers=headers).content, 'lxml')
        placeholders = set()
        email_placeholder(soup, placeholders)

        for scpt in soup.select('script'):
            scpt.decompose()

        for anchor in soup.findAll("a"):
            try:
                get_url = anchor.get('href')
                if domain_name not in get_url and not get_url.startswith('/'):
                    if re.search(PATTERN, get_url):
                        social_media.add(get_url)
                    continue
                else:
                    if get_url.startswith('/'):
                        get_url = base_url + get_url
                        if get_url not in unscraped:
                            unscraped.append(get_url)
                    else:
                        if get_url not in unscraped:
                            unscraped.append(get_url)
            except: pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(unscraped)) as executor:

            while len(unscraped):
                url = unscraped.popleft()  
                print(f"After pop: {len(unscraped)}")
                future_to_url = {executor.submit(scraped_url, url, scraped, headers, placeholders, about_emails, contact_emails, other_emails)}
                print(f"Future to URL: {future_to_url}")
        
        emails['Primary'] = list(about_emails)
        emails['Secondary'] = list(contact_emails)
        emails['Others'] = list(other_emails)
        emails = remove_unnecessary_mails(placeholders, emails, domain_name)
        print(emails)

        url_dct[domain_name] = emails
        url_dct['social_media'] = social_media
        url_json_arr.append(url_dct)

    pp.pprint(url_json_arr)
    result_xlsx = write_json_to_csv(url_json_arr, upload_dir_path)
    return result_xlsx