# -*- coding: utf-8 -*-

# 打卡脚修改自ZJU-nCov-Hitcarder的开源代码，感谢这位同学开源的代码

import requests
import json
import re
import datetime
import random
import time
import sys
import ddddocr


class ClockIn(object):
    """Hit card class
    Attributes:
        username: (str) 浙大统一认证平台用户名（一般为学号）
        password: (str) 浙大统一认证平台密码
        LOGIN_URL: (str) 登录url
        BASE_URL: (str) 打卡首页url
        SAVE_URL: (str) 提交打卡url
        HEADERS: (dir) 请求头
        sess: (requests.Session) 统一的session
    """
    LOGIN_URL = "https://zjuam.zju.edu.cn/cas/login?service=https%3A%2F%2Fhealthreport.zju.edu.cn%2Fa_zju%2Fapi%2Fsso%2Findex%3Fredirect%3Dhttps%253A%252F%252Fhealthreport.zju.edu.cn%252Fncov%252Fwap%252Fdefault%252Findex"
    BASE_URL = "https://healthreport.zju.edu.cn/ncov/wap/default/index"
    SAVE_URL = "https://healthreport.zju.edu.cn/ncov/wap/default/save"
    CAPTCHA_URL = 'https://healthreport.zju.edu.cn/ncov/wap/default/code'
    HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"
    }
    
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.sess = requests.Session()
        self.ocr = ddddocr.DdddOcr()

    def login(self):
        """Login to ZJU platform"""
        res = self.sess.get(self.LOGIN_URL, headers=self.HEADERS)
        execution = re.search(
            'name="execution" value="(.*?)"', res.text).group(1)
        res = self.sess.get(
            url='https://zjuam.zju.edu.cn/cas/v2/getPubKey', headers=self.HEADERS).json()
        n, e = res['modulus'], res['exponent']
        encrypt_password = self._rsa_encrypt(self.password, e, n)

        data = {
            'username': self.username,
            'password': encrypt_password,
            'execution': execution,
            '_eventId': 'submit'
        }
        res = self.sess.post(url=self.LOGIN_URL, data=data, headers=self.HEADERS)

        # check if login successfully
        if '统一身份认证' in res.content.decode():
            raise LoginError('登录失败，请核实账号密码重新登录')
        return self.sess

    def post(self):
        """Post the hitcard info"""
        res = self.sess.post(self.SAVE_URL, data=self.info, headers=self.HEADERS)
        return json.loads(res.text)

    def get_date(self):
        """Get current date"""
        today = datetime.date.today()
        return "%4d%02d%02d" % (today.year, today.month, today.day)

    def get_captcha(self):
        """Get CAPTCHA code"""
        resp = self.sess.get(self.CAPTCHA_URL)
        captcha = self.ocr.classification(resp.content)
        print("验证码：", captcha)
        return captcha

    def get_info(self, html=None):
        """Get hitcard info, which is the old info with updated new time."""
        if not html:
            res = self.sess.get(self.BASE_URL, headers=self.HEADERS)
            html = res.content.decode()

        try:
            old_infos = re.findall(r'oldInfo: ({[^\n]+})', html)
            if len(old_infos) != 0:
                old_info = json.loads(old_infos[0])
            else:
                raise RegexMatchError("未发现缓存信息，请先至少手动成功打卡一次再运行脚本")

            new_info_tmp = json.loads(re.findall(r'def = ({[^\n]+})', html)[0])
            new_id = new_info_tmp['id']
            name = re.findall(r'realname: "([^\"]+)",', html)[0]
            number = re.findall(r"number: '([^\']+)',", html)[0]
        except IndexError:
            raise RegexMatchError('Relative info not found in html with regex')
        except json.decoder.JSONDecodeError:
            raise DecodeError('JSON decode error')

        new_info = old_info.copy()
        new_info['id'] = new_id
        new_info['name'] = name
        new_info['number'] = number
        new_info["date"] = self.get_date()
        new_info["created"] = round(time.time())
        new_info['jrdqtlqk[]'] = 0
        new_info['jrdqjcqk[]'] = 0
        new_info['sfsqhzjkk'] = 1   # 是否申领杭州健康码
        new_info['sqhzjkkys'] = 1   # 杭州健康吗颜色，1:绿色 2:红色 3:黄色
        new_info['sfqrxxss'] = 1    # 是否确认信息属实
        new_info['jcqzrq'] = ""
        new_info['gwszdd'] = ""
        new_info['szgjcs'] = ""
        new_info['verifyCode'] = self.get_captcha()

        # 2021.08.05 Fix 2
        magics = re.findall(r'"([0-9a-f]{32})":\s*"([^\"]+)"', html)
        for item in magics:
            new_info[item[0]] = item[1]

        self.info = new_info
        return json.loads(old_info["geo_api_info"])["formattedAddress"]

    def _rsa_encrypt(self, password_str, e_str, M_str):
        password_bytes = bytes(password_str, 'ascii')
        password_int = int.from_bytes(password_bytes, 'big')
        e_int = int(e_str, 16)
        M_int = int(M_str, 16)
        result_int = pow(password_int, e_int, M_int)
        return hex(result_int)[2:].rjust(128, '0')


# Exceptions
class LoginError(Exception):
    """Login Exception"""
    pass


class RegexMatchError(Exception):
    """Regex Matching Exception"""
    pass


class DecodeError(Exception):
    """JSON Decode Exception"""
    pass


def main(username, password, times):
    """Hit card process
    Arguments:
        username: (str) 浙大统一认证平台用户名（一般为学号）
        password: (str) 浙大统一认证平台密码
    """

    #Beijing Time
    SHA_TZ = datetime.timezone(datetime.timedelta(hours=8),name='Asia/Shanghai',)
    beijing_now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).astimezone(SHA_TZ)
    print("\n[北京时间] %s" % beijing_now.strftime('%Y-%m-%d %H:%M:%S'))

    abort = True

    now = int(time.time())
    if ((now/3600 + 8) % 24) > 18: # 在北京时间18:00之后补打一次
        abort = False
        print("🚒补打一个")

    if abort:
        print("🎲考虑下打不打卡")
        rnd = random.randint(1, times)

        if rnd == times: # 在每天的<times>个时间点以<1/times>的概率执行打卡
            abort = False
            print("✅yesyes!")

    if abort:
        print("✅下次一定")
        sys.exit(0)
    

    print("🚌 打卡任务启动")

    dk = ClockIn(username, password)

    print("登录到浙大统一身份认证平台...")
    try:
        dk.login()
        print("✅已登录到浙大统一身份认证平台")
    except Exception as err:
        raise Exception("❌",str(err))

    print('正在获取个人信息...')
    try:
        location = dk.get_info()
        print("✅", location)
    except Exception as err:
        print('❌获取信息失败，请手动打卡，更多信息: ' + str(err))
        raise Exception

    print('正在为您打卡...')
    try:
        res = dk.post()
        if str(res['e']) == '1':
            if res['m'].find("已经") != -1: # 已经填报过了 不报错
                pass
            elif res['m'].find("验证码错误") != -1: # 验证码错误
                print('再次尝试')
                time.sleep(5)
                main(username, password)
                pass
            else:
                raise Exception("❌数据提交失败: "+res['m'])
        print("✅",res['m'])
    except Exception:
        print('❌数据提交失败')
        raise Exception


if __name__ == "__main__":
    username = sys.argv[1]
    password = sys.argv[2]
    times = sys.argv[3]
    try:
        main(username, password, int(times))
    except Exception as err:
        print(err)
