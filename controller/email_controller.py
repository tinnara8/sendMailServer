import sqlite3
from datetime import datetime
import smtplib
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import configparser


config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.ini')

# อ่าน config จากไฟล์ config.ini
config = configparser.ConfigParser()
config.read(config_path)

from_email = config['SMTP']['EMAIL_USER']
password = config['SMTP']['EMAIL_PASSWORD']
smtp_server = config['SMTP']['SMTP_SERVER']
smtp_port = int(config['SMTP']['SMTP_PORT'])


# sanitize ชื่อไฟล์ ที่ยาวและอักขระ ไม่น่ารัก
def sanitize_filename(filename):
    # จำกัดความยาวของชื่อไฟล์ (เช่น 50 อักขระ)
    max_length = 25
    base, ext = os.path.splitext(filename)
    
    # แทนที่อักขระพิเศษด้วย underscore (_)
    sanitized_base = re.sub(r'[^\w\-_.]', '_', base)
    sanitized_base = sanitized_base[:max_length]
    sanitized_filename = sanitized_base + ext
    return sanitized_filename

def send_email(to_email, subject, body, files=None):
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email  # ตรงนี้ยังเป็นการแสดงผล แต่จะใช้การส่งให้หลายอีเมล
    
    # แยกอีเมลผู้รับออกจากกันด้วยจุลภาค
    recipients = [email.strip() for email in to_email.split(',')]

    msg["Subject"] = subject

    # แนบข้อความในอีเมล
    msg.attach(MIMEText(body, "plain"))

    # แนบไฟล์หลายไฟล์
    if files:
        for file in files:
            original_filename = os.path.basename(file)
            sanitized_filename = sanitize_filename(original_filename)
            
            with open(file, "rb") as f:
                part = MIMEApplication(f.read(), Name=sanitized_filename)
                part.add_header('Content-Disposition', 'attachment', 
                                filename=('utf-8', '', sanitized_filename))
                msg.attach(part)

    # ส่งอีเมลไปยังผู้รับหลายคน
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_email, password)
        server.sendmail(from_email, recipients, msg.as_string())  # ส่งอีเมลไปยังหลายผู้รับ
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def get_db_path():
    current_month = datetime.now().strftime("%Y_%m")
    db_path = os.path.join('database', f'sendmail_{current_month}.sql')
    
    if not os.path.exists(db_path):
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS sendEmail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT NOT NULL,
                to_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                isp_name TEXT NOT NULL,
                result TEXT NOT NULL,
                time_taken REAL NOT NULL
            );''')
            cur.execute('''CREATE TABLE IF NOT EXISTS fileAttached (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sendEmailId INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_desc TEXT,
                file_type TEXT,
                FOREIGN KEY(sendEmailId) REFERENCES sendEmail(id) ON DELETE CASCADE
            );''')
            con.commit()
    return db_path

# ฟังก์ชันบันทึกข้อมูลการส่งอีเมล
def log_sendmail_to_db(datetime, to_email, subject, isp_name, result, time_taken, files):
    db_path = get_db_path()
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute('''INSERT INTO sendEmail (datetime, to_email, subject, isp_name, result, time_taken)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (datetime, to_email, subject, isp_name, result, time_taken))
        send_email_id = cur.lastrowid

        for file in files:
            file_name = file['name']
            file_size = file['size']
            file_desc = file['desc']
            file_type = file['type']
            cur.execute('''INSERT INTO fileAttached (sendEmailId, file_name, file_size, file_desc, file_type)
                           VALUES (?, ?, ?, ?, ?)''',
                        (send_email_id, file_name, file_size, file_desc, file_type))
        con.commit()