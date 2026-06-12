from plyer import notification
import os
import random
import re
import time
import requests
import tkinter as tk
from tkinter import simpledialog, messagebox

url = 'http://jw.xujc.com/student/index.php?c=Xk&a=List&id=1391'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
}

def prompt_phpsessid(default_value: str = '') -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    phpsessid = simpledialog.askstring('PHPSESSID 输入', '请输入 PHPSESSID:', initialvalue=default_value, parent=root)
    root.destroy()
    if not phpsessid:
        messagebox.showwarning('PHPSESSID 未输入', '未输入 PHPSESSID，程序将退出。')
        raise SystemExit('PHPSESSID required')
    return phpsessid.strip()

cookies = {
    'Hm_lvt_d4b4fe5895335a64dc71a1e3d97ecaae': '',
    'jgxy_jw_user': '',
    'jgxy_jw_lb': '',
    'PHPSESSID': prompt_phpsessid(''),
}

target_courses = [
    '沟通的艺术(MOOC)(1班) (职业技能类-职业技能类)',
    '沟通的艺术(MOOC)(2班) (职业技能类-职业技能类)',
    '组织行为与领导力(MOOC)(1班) (职业技能类-职业技能类)',
    '组织行为与领导力(MOOC)(2班) (职业技能类-职业技能类)',
]

# 每个页码是否请求该页，key 为页码，False 表示跳过
page_fetch_options = {
    1: False,  # 第 1 页通常包含一些固定课程，可以先不请求，后续如果需要再改成 True
    2: False,
    3: True,   # 第 3 页包含目标课程，默认请求
    4: False,
    5: True,   # 第 5 页包含目标课程，默认请求
    6: False,
}

# 获取 .py 文件所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

session = requests.Session()
session.headers.update(headers)
session.cookies.update(cookies)


def request_with_retry(method, url, headers=None, data=None, timeout=10, retries=3, delay=1.5):
    for attempt in range(1, retries + 1):
        resp = session.request(method, url, headers=headers, data=data, timeout=timeout)
        resp.encoding = 'gb2312'
        text = resp.text
        if not any(phrase in text for phrase in (
            '访问的页面过于频繁',
            '您访问的页面过于频繁',
            '本次请求过于频繁',
            '请稍候再试',
        )):
            return resp
        if attempt < retries:
            time.sleep(delay)
    return resp


def parse_hidden_inputs(html_text):
    hidden = {}
    for tag in re.findall(r'<input[^>]*type=["\']hidden["\'][^>]*>', html_text, flags=re.IGNORECASE):
        name_match = re.search(r'name=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        value_match = re.search(r'value=["\']([^"\']*)["\']', tag, flags=re.IGNORECASE)
        if name_match:
            hidden[name_match.group(1)] = value_match.group(1) if value_match else ''
    return hidden


def parse_page_numbers(html_text):
    pages = {1}
    pages.update(int(n) for n in re.findall(r"__doPostBack\('Page','(\d+)'\)", html_text))
    return sorted(pages)


def parse_courses(html_text):
    courses = []
    for tr in re.finditer(r'<tr>(.*?)</tr>', html_text, flags=re.S):
        row = tr.group(1)
        title_match = re.search(r'<a href="javascript:toggle\(\'[^\']+\'\)">([^<]+)</a>', row)
        add_match = re.search(r"__doPostBack\('Add','(\d+)'\)", row)
        if title_match and add_match:
            title = title_match.group(1).strip()
            add_id = add_match.group(1)
            selectable = 'disabled' not in row
            courses.append({
                'title': title,
                'id': add_id,
                'selectable': selectable,
                'row': row,
            })
    return courses


def get_page(page_num, hidden_inputs=None):
    time.sleep(random.uniform(5, 7))
    if page_num == 1:
        resp = request_with_retry('GET', url, headers={'Referer': url}, timeout=10)
        html = resp.text
        content = resp.content
        hidden = parse_hidden_inputs(html)
        return html, content, hidden

    data = hidden_inputs.copy() # type: ignore
    data['__EVENTTARGET'] = 'Page'
    data['__EVENTARGUMENT'] = str(page_num)
    resp = request_with_retry('POST', url, headers={'Referer': url}, data=data, timeout=10)
    html = resp.text
    content = resp.content
    hidden = parse_hidden_inputs(html)
    return html, content, hidden


def select_course(course_id, hidden_inputs):
    time.sleep(random.uniform(5, 7))
    data = hidden_inputs.copy()
    data['__EVENTTARGET'] = 'Add'
    data['__EVENTARGUMENT'] = course_id
    resp = request_with_retry('POST', url, headers={'Referer': url}, data=data, timeout=10)
    return resp


def course_status_text(course):
    return '可选' if course['selectable'] else '已满'


def scan_for_target():
    print('目标课程：', ', '.join(target_courses))
    page1_html, page1_content, hidden_inputs = get_page(1)
    page_numbers = list(range(1, 7))
    print('默认页面范围: 1-6')

    current_hidden = hidden_inputs
    found_course = False
    selected_course = None
    course_statuses = {title: '未找到' for title in target_courses}

    for page_num in page_numbers:
        if not page_fetch_options.get(page_num, True):
            print(f'跳过第 {page_num} 页获取')
            continue

        html, content, current_hidden = get_page(page_num, current_hidden)
        filename = os.path.join(SCRIPT_DIR, f'response_page{page_num}.html')
        with open(filename, 'wb') as f:
            f.write(content)
        print(f'已保存第 {page_num} 页：{filename} (长度 {len(content)})')
        if len(content) < 5000:
            print(f'警告：第 {page_num} 页内容长度异常，可能已经被教务系统禁止访问，程序已终止。')
            notification.notify(
                title="程序异常",
                message="可能已经被教务系统禁止访问，已自动终止",
                app_name="Class 1.0",
                timeout=10, # 通知显示时间（秒）
            ) # type: ignore
            break

        courses = parse_courses(html)
        for course in courses:
            if course['title'] in target_courses:
                found_course = True
                course_statuses[course['title']] = course_status_text(course)
                print(f'找到目标课程：{course["title"]}，页码 {page_num}，Add ID={course["id"]}，状态={course_status_text(course)}')
                if course['selectable'] and selected_course is None:
                    print('目标课程可选，执行自动选课请求...')
                    resp = select_course(course['id'], current_hidden)
                    print('选课请求 HTTP 状态:', resp.status_code)
                    print('选课结果片段:', resp.text[:400])
                    if resp.status_code == 200 : #and '选课成功' in resp.text
                        selected_course = course['title']
                        return selected_course, course_statuses
                    else:
                        print('选课请求未返回成功结果，继续扫描。')
    return selected_course, course_statuses


random.seed()
attempt = 0
scan_count = 0
selected_course = None
course_statuses = {title: '未找到' for title in target_courses}

while selected_course is None:
    attempt += 1
    scan_count += 1
    print(f'\n第 {attempt} 次扫描，时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
    selected_course, course_statuses = scan_for_target()
    if selected_course:
        break
    if scan_count % 6 == 0:
        print('已执行 6 次扫描，休息 40 秒后继续...')
        time.sleep(40)
    else:
        sleep_seconds = random.uniform(10, 12)
        print(f'未成功选课，等待 {sleep_seconds:.2f} 秒后重试...')
        time.sleep(sleep_seconds)

print('\n课程状态汇总：')
for title, status in course_statuses.items():
    print(f'- {title}: {status}')

if selected_course:
    print(f'已自动选中：{selected_course}')
    notification.notify(
        title="选课完成",
        message=f"已选中：{selected_course}",
        app_name="Class 1.0",
        timeout=10, # 通知显示时间（秒）
    ) # type: ignore
    
else:
    print('目标课程存在，但均已满或不可选，或尚未成功选课。')

