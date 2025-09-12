import smtplib
from email.mime.text import MIMEText
from email.utils import make_msgid
from datetime import datetime
import time
import serial
import csv
import os
 
EMAIL_SENDER = 'dropboxhcs@gmail.com'
EMAIL_PASSWORD = ''  # app pw from Gmail
EMAIL_RECIPIENT = 'housit1@mcmaster.ca'
RELAY_PORT = 'COM4'   # USB relay COM port
ESP32_PORT = 'COM5'   # ESP32 COM port
LOG_FILE = 'tap_log.csv'

# try to connect to relay: an initial check to make sure that the USB relay connected to maglocks is working and can be talked to
try:

    relay = serial.Serial(RELAY_PORT, 9600, timeout=1)
    time.sleep(2)
    print(f"Relay connected on {RELAY_PORT}")

except Exception as e:

    print(f"couldn't open relay port: {e}")
    relay = None

# try to connect to the ESP32
try:

    esp32 = serial.Serial(ESP32_PORT, 115200, timeout=0.1) # baud is 115200
    time.sleep(2)
    print(f"ESP32 on {ESP32_PORT} says hi")
    if esp32:
        esp32.reset_input_buffer()

except Exception as e:

    print(f"ESP32? nope: {e}") # doesn’t work
    esp32 = None

# makes and sends an email when card is tapped. Formats an email body with the card UID and timestamp.
def sendEmail(cardUid, timestamp):

    body=(
        f"Keycard scanned at dropbox.\n\n"
        f"Time: {timestamp}\n"
        f"Card UID: {cardUid}\n"
    )

    msg = MIMEText(body)
    msg['Subject'] = 'Guest Checkout Info'
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    mid = make_msgid()
    msg['Message-ID'] = mid
 
    try:

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.send_message(msg)
        print(f"sent email for {card_uid} @ {timestamp}")
        return mid
    
    except Exception as e:

        print(f"email fail: {e}")
        return None

# if card is confirmed by IR sensor, reply email is sent. Keeps the drops in order
def sendReply(original_mid):

    msg = MIMEText("Card drop confirmed.\n")
    msg['Subject'] = 'Re: Guest Checkout Info'
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT

    if original_mid:

        msg['In-Reply-To'] = original_mid
        msg['References'] = original_mid

    try:

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.send_message(msg)
        print("sent confirmation")

    except Exception as e:

        print(f"couldn't send confirmation: {e}")

# unlock maglocks through USB relay
def unlockRelay():

    if relay:
        try:
            relay.write(b'\xA0\x01\x01\xA2')
            print("maglock unlocked")
        except Exception as e:
            print(f"relay unlock fail: {e}")

# locks maglocks through USB relay
def lockRelay():
    if relay:
        try:
            relay.write(b'\xA0\x01\x00\xA1')
            print("maglock locked (hopefully)")
        except Exception as e:
            print(f"relay lock fail: {e}")

# csv logging file: makes new or adds new line
def log_tap(card_uid, timestamp):

    newfile = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, 'a', newline='') as f:
        w = csv.writer(f)
        if newfile:
            w.writerow(['Timestamp', 'Card UID'])
        w.writerow([timestamp, card_uid])

 
# Dropbox is now initialized
print("\n=== Waiting for card taps ===\n")
 
try:
    while True:
        card_uid = input("Tap card (enter UID): ").strip() # takes card tap UID
        if not card_uid:
            print("no UID")
            continue
 
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msgid = sendEmail(card_uid, now)
        log_tap(card_uid, now)
 
        unlockRelay()
 
        dropped = False
        t0 = time.time()
        ignore_until = t0 + 0.5 # ignore first bit of noise 0.5 seconds IMPORTANT
 
        while time.time() - t0 < 7: # 7 seconds to drop card (standard door lock time)
            if esp32 and esp32.in_waiting:
                line = esp32.readline().decode('utf-8', errors='ignore').strip()
                if line == "CARD_DETECTED":
                    if time.time() >= ignore_until and not dropped:
                        dropped = True
                        print("IR says card dropped -> replying")
                        sendReply(msgid)
            time.sleep(0.05) # IMPORTANT
 
        lockRelay()
 
        if not dropped:
            print("No drop detected")
        print("---\n")
 
except KeyboardInterrupt: # shutoff sequence
    if relay: relay.close()
    if esp32: esp32.close()