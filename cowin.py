try:
    from bs4 import BeautifulSoup
    from datetime import datetime
    import subprocess
    import requests
    import hashlib
    import base64
    import time
    import json
    import fire
    import sys
    import re
    import os
except ImportError:
    print("First run requirements instaling command")
    print("pip install -r requirements.txt")
    exit()

OTP_SITE_URL = None
OTP_VALID_DURATION_SECONDS = 180
''' 
Add Worker Domain here in Double Quore example : "https://db.domain.workers.dev"
Check this :  https://github.com/truroshan/CloudflareCoWinDB
'''

# scheduler = BlockingScheduler()

def line_break(): print("-"*25)

def clear_screen(): os.system('clear' if os.name =='posix' else 'cls')
      
class CoWinBook():

    def init(
        self, 
        mobile_no, # --m
        pin = "Not Passed", # --p
        age = 18 , # --a
        vaccine = "ANY", # --v
        dose = 1, # --d
        otp = 'a',  # --o
        time = 30, # --t
        bookToday = 1, # --b
        fee_type = "BOTH", # --f
        relogin = None  # --r
        ):

        self.mobile_no = str(mobile_no)
        if relogin and os.path.exists(self.mobile_no): os.remove(self.mobile_no)

        # Cron Time
        global TIME
        TIME = time

        # Include today session for Booking Slot
        self.bookToday =  0 if bookToday is True else 1


        self.center_id = []  # Selected Vaccination Centers
        self.user_id = []  # Selected Users for Vaccination 

        # Vaccination Center id and Session id for Slot Booking
        self.vaccine = vaccine.upper()
        self.vacc_fee_type = fee_type.upper()
        self.vacc_center = None
        self.vacc_session = None
        self.slot_time = None

        # Dose 1 or Dose 2 ( default : 1)
        self.dose = 2 if dose >= 2 else 1

        # OTP Fetching method 
        self.otp = otp

        # User Age 18 or 45
        self.age =  18 if age < 45 else 45
        
        # Request Session
        self.session =  requests.Session() 
        self.requestStatus = 0

        # Data for sending request
        self.data = {} 

        # Token Recieved from CoWIN
        self.bearerToken = None  # Session Token

        self.todayDate = datetime.now().strftime("%d-%m-%Y")

        # Login and Save Token in file( filename same as mobile no)
        self.getSession()

        self.checkByPincode = False
        if type(pin) is int:
            self.pin = pin # Area Pincode or District Id
            self.checkByPincode = True if len(str(pin)) == 6 else False
        else:
            self.pin = self.get_district_id()
        
        
        # Selecting Center and User
        self.setup_details()

        bottomBanner =  "for Today and Day After 📆 ..." if self.bookToday == 0 else "for Tomorrow and Day After 📆 ..."
        print(f" 📍 {self.pin} 💉 {age}+ ⌛️ {TIME} Seconds")
        print(f" 📲 XXXX{self.mobile_no[7:]} 💉 {self.vaccine} (Dose :{self.dose})")
        print(f"CoWin Auto Slot Booking 🔃\n{bottomBanner}")
        line_break()

    # Set Header in self.session = requests.Session()
    def set_headers(self):
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Mobile Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'Origin': 'https://selfregistration.cowin.gov.in',
            'Connection': 'keep-alive',
            'Referer': 'https://selfregistration.cowin.gov.in/',
            'TE': 'Trailers',
        })

    # returning self.data 
    def get_data(self):
        return json.dumps(self.data).encode('utf-8')

    # Save Token after login to CoWIN
    def putSession(self):
        with open(self.mobile_no, "w") as f:
            f.write(self.bearerToken)

    # Get Token saved in file for relogin and use
    def getSession(self):
        
        self.set_headers()
        try:
            with open(self.mobile_no, "r") as f:
                self.bearerToken = f.read()
            self.session.headers.update({
                    'Authorization': 'Bearer {}'.format(self.bearerToken)
                })
            self.fetch_beneficiaries().json()
        except (FileNotFoundError,json.decoder.JSONDecodeError):
            self.login_cowin()
        
    def checkToken(self):
        # Pause job of Checking Slot
        # scheduler.pause_job('slot')
        
        response = self.fetch_beneficiaries()
        try:
            response.json()
        except json.decoder.JSONDecodeError:
            self.login_cowin()

        # Resume job of Checking Slot
        # scheduler.resume_job('slot')

    # Login to selfregistration.cowin.gov.in/
    def login_cowin(self):

        self.data = {
        "secret":"U2FsdGVkX1+gGN13ULaCVtLSWmsyZwAdXXTIAvLQp2HOXrIBCcq0yyOZQqzzfiFiEYs7KoAOTK2j4qPF/sEVww==",
        "mobile": self.mobile_no
            }

        response = self.session.post('https://cdn-api.co-vin.in/api/v2/auth/generateMobileOTP',data=self.get_data())

        if self.otp == 's' and OTP_SITE_URL is not None: requests.delete(f"{OTP_SITE_URL}/{self.mobile_no}")

        otpSha265 = self.get_otp()
        try:
            txn_id = response.json()['txnId']
        except json.decoder.JSONDecodeError:
            print("Wrong OTP Entered")
            return

        self.data = {
                        "otp":otpSha265,
                        "txnId": txn_id
                                    }
        
        response = self.session.post('https://cdn-api.co-vin.in/api/v2/auth/validateMobileOtp',data=self.get_data())
        
        self.bearerToken = response.json()['token']

        self.session.headers.update({
            'Authorization': 'Bearer {}'.format(self.bearerToken)
        })
        self.putSession() 

    # Request for OTP 
    def get_otp(self):
        
        otp_fetching_mode = ""
        if self.otp == 'a':
            otp_fetching_mode = 'Auto Mode'
        elif self.otp == 's':
            otp_fetching_mode = 'Site Mode'
        else:
            otp_fetching_mode = "Manual Mode"

        print(f"OTP Sent ({otp_fetching_mode}) 📲 ... ")

        otp = ""

        try:    
            curr_msg = self.get_msg()
            curr_msg_body = curr_msg.get("body")

            for i in reversed(range(30)):
            
                last_msg = self.get_msg()
                last_msg_body = last_msg.get("body",'')
            
                print(f'Waiting for OTP {i} sec')
                self.set_cursor()

                d1 = datetime.strptime(last_msg.get("received","2019-12-01 09:09:09"), '%Y-%m-%d %H:%M:%S')
                d2 = datetime.now() # current date and time
                diff = (d2 - d1).total_seconds()
                if (curr_msg_body != last_msg_body and "cowin" in last_msg_body.lower()) or diff <= OTP_VALID_DURATION_SECONDS:
                    otp = re.findall("(\d{6})",last_msg_body)[0]
                    print("\nOTP Recieved : ",otp)
                    break

                time.sleep(1)
        except (Exception,KeyboardInterrupt) as e:
            print(e)
       
        if not otp: otp = input("\nEnter OTP : ")

        return hashlib.sha256(otp.encode('utf-8')).hexdigest()

    # Get Mobile last msg for otp Checking  
    def get_msg(self):
        msg = {}

        # Get OTP using Termux:API v0.31 
        if self.otp == 'a':
            msg = subprocess.Popen(
                                    'termux-sms-list -l 1',
                                    stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,shell=True).communicate()[0].decode('utf-8')
            try:
                msg = json.loads(msg)[0]
                return msg
            except KeyError:
                raise Exception("Install Termux:API from FDroid for Auto Mode  ")
        
        # Get OTP using DB hosted on Cloudflare and Configure with https://play.google.com/store/apps/details?id=com.gawk.smsforwarder
        elif self.otp == 's':

            if OTP_SITE_URL is None:
                raise Exception("First Setup DB on Cloudflare \nhttps://github.com/truroshan/CloudflareCoWinDB ")

            res = requests.get(f"{OTP_SITE_URL}/{self.mobile_no}").json()
                
            if res.get("status"):
                msg['body'] = res.get('data').get("message")
                requests.delete(f"{OTP_SITE_URL}/{self.mobile_no}")
            return msg

        # Lastly enter OTP Manually
        raise Exception
        
    # Request for Current Slot Deatails ( Private Request )
    def request_slot(self):
        todayDate = datetime.now().strftime("%d-%m-%Y")

        if self.checkByPincode:
            response = self.session.get(f'https://cdn-api.co-vin.in/api/v2/appointment/sessions/calendarByPin?pincode={self.pin}&date={todayDate}')
        else: # Check by District
            response = self.session.get(f'https://cdn-api.co-vin.in/api/v2/appointment/sessions/calendarByDistrict?district_id={self.pin}&date={todayDate}')
        
        status =  response.status_code

        if status == 200:
            self.check_slot(response.json())
        elif status == 401:
            print("Re-login Account : " + datetime.now().strftime("%H:%M:%S") + " 🤳")
            self.checkToken()
            self.request_slot()
        else:
            self.requestStatus += 1
            if self.requestStatus >= 4:
                self.requestStatus = 0
                self.login_cowin()
                time.sleep(7)

        # When last Checked
        print(f'''Last Checked {status} {"✅" if status == 200 else "⚠️" } : ''' + datetime.now().strftime("%H:%M:%S") + " 🕐")
        self.set_cursor()

    # Check Slot availability 
    def check_slot(self,response):

        centers = response.get('centers',[])
        for center in centers:
            
            for session in center.get('sessions')[self.bookToday:]:
                
                self.vacc_center = center.get('center_id')
                self.vacc_session = session.get("session_id")

                center_name = center.get('name')
                capacity = session.get(f'available_capacity_dose{self.dose}')
                session_date = session.get('date')
                
                vaccine_name = session.get('vaccine')

                if capacity > 0 and \
                    (self.vaccine in vaccine_name or self.vaccine == "ANY") and \
                    session.get('min_age_limit') == self.age and \
                    ( center.get('center_id') in  self.center_id or not self.center_id):

                    self.slot_time = session.get('slots')[0]

                    MSG = f'💉 {capacity} #{vaccine_name} / {session_date} / {center_name} 📍{self.pin}'

                    # Send Notification via Termux:API App
                    os.system(f"termux-notification --content '{MSG}'")
                
                    BOOKED = self.book_slot()
                    if BOOKED:
                        # scheduler.shutdown(wait=False)
                        print("Shutting Down CoWin Script 👩‍💻 ")
                        exit()

    # Get Solved Captcha in String
    def get_captcha(self):

        model = "eyJNTExRTExRTExRTExMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTExRTExRWk1MTFFMTFFMTFFMTFFaIjogIjAiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTFoiOiAiMSIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExMUUxMTFFMTFFaIjogIjIiLCAiTUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTExMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExMUUxMUUxMUUxMUUxMUUxMUUxMTExRTExRTExRTExRTExRTExRTExMTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiMyIsICJNTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRWk1MTFFMTExRTExRTExRTExRTExRTExRTExMUUxMTFFMTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRWiI6ICI0IiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMTExMUUxMTFFMTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTExRTExRTExRTExRTExRWiI6ICI1IiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogIjYiLCAiTUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRTExRTExMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFaTUxMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMTExRTExRTExRTExRTExRTExMUUxMTFFMTFFMTFFMTExRWiI6ICI3IiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExMUUxMUUxMUUxMUUxMTExMUUxMUUxMUUxMUUxMTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExMUUxMUUxMUUxMUUxMUUxMUVoiOiAiOCIsICJNTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogIjkiLCAiTUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUVpNTExMUUxMUUxMUUxMUUxMUUxMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTExRWiI6ICJBIiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUVpNTExRTExRTExRTExRTExMUUxMUUxMUUxMUVpNTExMUUxMTExMUUxMTFFMTFFMTFFMTFFMTFFMTFFaIjogIkIiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiQyIsICJNTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogIkQiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogIkUiLCAiTUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUVoiOiAiRiIsICJNTExRTExRTExRTExMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMWiI6ICJHIiwgIk1MTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWiI6ICJIIiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAibCIsICJNTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWiI6ICJKIiwgIk1MTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMTExMUVpNTExRTExRTExRTExMUUxMUUxMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWiI6ICJLIiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiTCIsICJNTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRWiI6ICJNIiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMWk1MTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiTiIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExRWiI6ICJPIiwgIk1MTFFMTFFMTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFaIjogIlAiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTExRTExMUUxMUUxMUUxMUUxMUVpNTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTExMTFFMTFFMTFFaIjogIlEiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMTFFMTFFMTFFaTUxMTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFaTUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogIlIiLCAiTUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiUyIsICJNTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWiI6ICJUIiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogIlUiLCAiTUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogIlYiLCAiTUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiVyIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFaIjogIlgiLCAiTUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFoiOiAiWSIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMTFFMTFFMTFFMTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRWiI6ICJaIiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRWk1MTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogImEiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRWiI6ICJiIiwgIk1MTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExMUUxMUUxMUVoiOiAiYyIsICJNTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiZCIsICJNTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTExRWk1MTFFMTFFMTFFMTFFMTFFaTUxMUUxMTExRTExRTExRWiI6ICJlIiwgIk1MTFFMTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFaTUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRTExRTExMUUxMTExRTExRTExMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogImYiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMTFFMTExRTExRTExRTExMUUxMUUxMUUxMUUxMTExRTExRTExRTExRTExRTExMUUxMTFFMTFFMTExRTExMUVpNTExRTExRTExRTExRTExRTExRTExRTExRWiI6ICJnIiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExMUUxMUVoiOiAiaCIsICJNTExRTExMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTFpNTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUVpNTExMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogImkiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExMUUxMUUxMUUxMUUxMUUxMTFFMTExMUUxMUVpNTExMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiaiIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAiayIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTExRTExRWk1MTExaIjogIm0iLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAibiIsICJNTExRTExRTExRTExRTExRTExRTExRWk1MTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAibyIsICJNTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExMUUxMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMTExMUUxMTFFMTFFMTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxaTUxMUUxMUUxMUUxMUUxMTFFMTExRTExMUUxMUVoiOiAicCIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFaTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVoiOiAicSIsICJNTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExaTUxMTFoiOiAiciIsICJNTExMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMTExRTExRTExRTExMUUxMUVoiOiAicyIsICJNTExRTExRTExRTExRTExMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFaTUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTExRTExRTExRWiI6ICJ0IiwgIk1MTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMTExMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogInUiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTExRTExMUVoiOiAidiIsICJNTExRTExMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFMTFFMTFFMTFFMTExRWk1MTFFMTFFMTFFMTFFMTFFMTExRTExRTExRTExRTExMUUxMTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMWiI6ICJ3IiwgIk1MTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRWk1MTFFMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMTFFaIjogIngiLCAiTUxMUUxMUUxMUUxMUUxMUUxMUUxMUUxMTFFMTFFaTUxMUUxMTFFMTFFMTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMUVoiOiAieSIsICJNTExRTExRTExRTExRTExRTExRTExRTExMUUxMUUxMUUxMUUxMUUxMUVpNTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExRTExMUUxMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFMTFFaIjogInoifQ=="
        
        # Send request for Captcha    
        data = '{}'
        response = self.session.post('https://cdn-api.co-vin.in/api/v2/auth/getRecaptcha', data=data)

        if not response.ok:
            self.login_cowin()
            return self.get_captcha()

        # Get Captcha Data from Json
        svg_data = response.json()['captcha']


        soup = BeautifulSoup(svg_data,'html.parser')

        model = json.loads(base64.b64decode(model.encode('ascii')))
        CAPTCHA = {}

        for path in soup.find_all('path',{'fill' : re.compile("#")}):

            ENCODED_STRING = path.get('d').upper()
            INDEX = re.findall('M(\d+)',ENCODED_STRING)[0]

            ENCODED_STRING = re.findall("([A-Z])", ENCODED_STRING)
            ENCODED_STRING = "".join(ENCODED_STRING)

            CAPTCHA[int(INDEX)] =  model.get(ENCODED_STRING)

        CAPTCHA = sorted(CAPTCHA.items())
        CAPTCHA_STRING = ''

        for char in CAPTCHA:
            CAPTCHA_STRING += char[1]

        return CAPTCHA_STRING

    # Book Slot for Vaccination
    def book_slot(self):
        
        # CoWIN Removed Captcha
        # captcha = self.get_captcha()

        self.data = {
            "center_id":self.vacc_center ,
            "session_id":self.vacc_session,
            "beneficiaries":self.user_id,
            "slot":self.slot_time,
            # "captcha": captcha,
            "dose": self.dose
            }

        response = self.session.post('https://cdn-api.co-vin.in/api/v2/appointment/schedule',data=self.get_data())

        status =  response.status_code
        
        if status == 200:
            print("🏥 Appointment scheduled successfully! 🥳 ")
            return True
        elif status == 409:
            print("This vaccination center is completely booked for the selected date 😥")
        elif status == 400:
            print("Minimum age criteria is 45 years  for this center")
        elif status == 401:
            self.login_cowin()
            self.book_slot()
        else:
            print("Error in Booking Slot")
            print(f'{status} : {response.json()}')

    # Booking Method
    def book_now(self):
        self.request_slot()

    # Set details about Vaacination Center and User Id
    def setup_details(self):
        self.select_beneficiaries()
        self.select_center()
        

    # Get District Id
    def get_district_id(self):
        response = self.session.get("https://cdn-api.co-vin.in/api/v2/admin/location/states").json()

        print("Select State : ")
        for state in response.get("states",):
            state_id = state.get("state_id")
            state_name = state.get('state_name')
            print(f"{state_id} : {state_name}")
        
        index = input("Enter Index : ")
        clear_screen()
        response =  self.session.get(f"https://cdn-api.co-vin.in/api/v2/admin/location/districts/{index}").json()

        print("Select District : ")
        for dist in response.get("districts"):
            dist_id = dist.get("district_id")
            dist_name = dist.get('district_name')
            print(f"{dist_id} : {dist_name}")
        
        index = input("Enter Index : ")
        
        clear_screen()
        return index

    def fetch_center(self):
        if self.checkByPincode:
            response = self.session.get(
                f'https://cdn-api.co-vin.in/api/v2/appointment/sessions/calendarByPin?pincode={self.pin}&date={self.todayDate}'
                )
        else: # Check by District
            response = self.session.get(
                f'https://cdn-api.co-vin.in/api/v2/appointment/sessions/calendarByDistrict?district_id={self.pin}&date={self.todayDate}'
                )
        return response

    # Select Center for Vaccination
    def select_center(self):
        response = self.fetch_center()

        while response.status_code != 200:
            print(f'Trying to fetch center detail. Please wait...')
            self.set_cursor()
            time.sleep(5)
            response = self.fetch_center()
        clear_screen()
        
        response = response.json()

        CENTERS = {}
        INDEX_S = []
        
        if not response.get('centers'):
            print("No Centers Available at this location")
            print("Shutting Down CoWin Script 👩‍💻 ")
            exit()

        print(f"Select Vaccination Center ({self.pin}) 💉 \n")

        counter = 1
        for center in response.get('centers',[]):
            vaccine_fee_type =  center.get("fee_type").upper()
            vaccine__fee_emoji = '🆓' if "FREE" in vaccine_fee_type else '💰'
            
            for session in center.get('sessions'):
                vaccine_name = session.get("vaccine")
                
                if session.get('min_age_limit') == self.age \
                    and (self.vaccine in vaccine_name or self.vaccine == 'ANY') \
                    and (self.vacc_fee_type in vaccine_fee_type or self.vacc_fee_type == "BOTH" ):

                    print(f'{counter} : {center.get("name")} {vaccine__fee_emoji}')
                    CENTERS[counter] = center.get('center_id')
                    INDEX_S.append(counter)
                    counter += 1
                    break
            
        if counter == 1:
            # clear_screen()
            print(f"No {self.age}+ Centers available at this time.\nVaccine Type : {self.vaccine} 💉  Fee Type : ({self.vacc_fee_type}).")
            line_break()
            print(f"If you still want to book slot 😌.")
            print(f"**Script will book at any center in this pin({self.pin}) 📍 ")
            yes = input("\nPress📲 Y(enter)/N: ")
            if yes.upper() == "N":
                self.shutting_down()
                exit()
            clear_screen()
            return

        print()
        line_break()
        print("""
    * Select One Center
        input : 1
    * Select Mutiple with Space
        input : 1 2 3 4
    * Select All Center
        Hit Enter without Input
    
   **pass --f paid or free
   **pass --v vacc_name \n""")

        line_break()

        input_index = input("Enter Index's : ")

        if input_index != '':
            INDEX_S = re.findall("(\d+)",input_index)
            
        clear_screen()

        CENTER_ID = []
        for  index in INDEX_S:
            if CENTERS.get(int(index)):
                CENTER_ID.append(CENTERS.get(int(index)))
        self.center_id = CENTER_ID

    def fetch_beneficiaries(self):
        return self.session.get('https://cdn-api.co-vin.in/api/v2/appointment/beneficiaries')

    # Select User to Book Slot
    def select_beneficiaries(self):

        response = self.fetch_beneficiaries()
        while response.status_code != 200:
            print(f'Please wait...')
            self.set_cursor()
            time.sleep(5)
            response = self.fetch_beneficiaries()
        
        response = response.json()

        USERS = {}
        INDEX_S = []

        print(f"Select User for Vaccination 👩‍👦‍👦 \n")

        if not response.get('beneficiaries',[]):
            print("No beneficiaries added  in Account")
            exit()

        counter = 1
        for user in response.get('beneficiaries'):
            if not user.get(f'dose{self.dose}_date'):
                print(f'{counter} : {user.get("name")}')
                USERS[counter] = user.get('beneficiary_reference_id')
                INDEX_S.append(counter)
                counter += 1


        if counter == 1:
            # clear_screen()
            print(f"No beneficiaries available for Dose {self.dose}.")
            self.shutting_down()
            exit()

        print()
        line_break()
        print("""
    * Select One User
        input : 1
    * Select Mutiple User with Space
        input : 1 2 3 4
    * Select All User
        Hit Enter without Input\n""")

        line_break()

        input_index = input("Enter Index's : ")

        if input_index != '':
            INDEX_S = re.findall("(\d)",input_index)
            
        clear_screen()

        USER_ID = []
        for index in INDEX_S:
            if USERS.get(int(index)):
                USER_ID.append(USERS.get(int(index)))

        self.user_id = USER_ID

    def shutting_down(self):
        print("Shutting Down CoWin Script 👩‍💻 ")

    def set_cursor(self):
        sys.stdout.write("\033[F")


if __name__ == '__main__':

    clear_screen()

    cowin = CoWinBook()
    
    fire.Fire(cowin.init)
 
    # Check for Slot
    # scheduler.add_job(cowin.book_now, 'interval',id = "slot",seconds = TIME, misfire_grace_time=2,replace_existing=True)
    # schedule.every(TIME).seconds.do(cowin.book_now)
    
    # Check Token every 3 min
    # scheduler.add_job(cowin.checkToken, 'cron',id ="login", minute = f'*/3',misfire_grace_time= 30)
    # schedule.every(3).minutes.do(cowin.checkToken)

    # scheduler.start()

    # while True:
    # schedule.run_pending()
        # time.sleep(1)
    
    while True:
        timeObj = datetime.now()
        _min, _sec = timeObj.minute , timeObj.second
        
        if _min % 3 == 0:
            cowin.checkToken()
        
        if _sec % TIME == 0:
            cowin.book_now()

        time.sleep(1)
