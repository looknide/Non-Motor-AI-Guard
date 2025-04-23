from flask import Flask, Response
import cv2

app = Flask(__name__)

cap = cv2.VideoCapture(0)  # 打开摄像头

def gen_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            # 编码为JPEG格式
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            # 用multipart方式传输给前端
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    # 返回多部分响应，MIME类型是 mjpeg
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
