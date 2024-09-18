import os
import tempfile
import time
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
import sqlite3
from datetime import datetime
from controller.email_controller import send_email, log_sendmail_to_db

app = Flask(__name__)
socketio = SocketIO(app)

# เก็บข้อมูลการส่งอีเมล
email_logs = []

# ฟังก์ชันสำหรับดึงข้อมูลจากฐานข้อมูล
def get_all_logs():
    logs = []
    for db_file in os.listdir('database'):
        if db_file.endswith('.sql'):
            db_path = os.path.join('database', db_file)
            with sqlite3.connect(db_path) as con:
                cur = con.cursor()
                
                # ดึงข้อมูลจากตาราง sendEmail
                cur.execute('SELECT * FROM sendEmail')
                send_email_logs = cur.fetchall()

                for email_log in send_email_logs:
                    send_email_id = email_log[0]  # ดึง sendEmailId
                    
                    # ดึงข้อมูลจากตาราง fileAttached ที่สัมพันธ์กับ sendEmailId
                    cur.execute('SELECT file_name, file_size FROM fileAttached WHERE sendEmailId = ?', (send_email_id,))
                    attached_files = cur.fetchall()
                    
                    # จัดรูปแบบไฟล์แนบ
                    files = [{'file_name': file[0], 'file_size': file[1]} for file in attached_files]
                    
                    # สร้าง log ที่รวมข้อมูลไฟล์แนบ
                    log = {
                        'datetime': email_log[1],
                        'to_email': email_log[2],
                        'subject': email_log[3],
                        'isp_name': email_log[4],
                        'result': email_log[5],
                        'time_taken': email_log[6],
                        'files': files
                    }
                    logs.append(log)
    return logs


@app.route("/send_email", methods=["POST"])
def api_send_email():
    data = request.form
    to_email = data.get("to_email")  # รับหลายอีเมลในรูปแบบ "email1@example.com, email2@example.com"
    subject = data.get("subject")
    isp_name = data.get("isp_name")
    result = data.get("result")
    files = request.files.getlist("file")  # รับหลายไฟล์

    if not to_email or not subject or not result:
        return jsonify({"error": "Missing required fields"}), 400

    current_datetime = time.strftime("%d/%m/%Y %I:%M %p")
    start_time = time.time()

    email_body = (
        f"Date/Time: {current_datetime}\n"
        f"ISP Name: {isp_name}\n"
        f"Scan Results:\n{result}\n"
    )

    temp_files = []
    for file in files:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)
        temp_files.append({
            'path': file_path,
            'name': file.filename,
            'size': os.path.getsize(file_path),
            'desc': 'Description for ' + file.filename,  # คุณสามารถกำหนดเองได้
            'type': file.content_type  # ประเภทของไฟล์
        })

    email_sent = send_email(to_email, subject, email_body, [f['path'] for f in temp_files])

    end_time = time.time()
    time_taken = end_time - start_time

    if email_sent:
        log_sendmail_to_db(current_datetime, to_email, subject, isp_name, result, time_taken, temp_files)

        logs = get_all_logs()
        socketio.emit('logs_update', logs)

        return jsonify({"message": "Email sent successfully!"}), 200
    else:
        return jsonify({"error": "Failed to send email"}), 500
    

# หน้าแดชบอร์ดแสดงการส่งอีเมล
@app.route("/email_dashboard")
def email_dashboard():
    return render_template('dashboard.html')

# ฟังก์ชันสำหรับส่งข้อมูลแบบ real-time
@socketio.on('fetch_logs')
def handle_fetch_logs():
    logs = get_all_logs()
    socketio.emit('logs_update', logs)

if __name__ == "__main__":
    # app.run(debug=True)
    socketio.run(app, debug=True)
