import cv2
import numpy as np

vc = cv2.VideoCapture(1)

while cv2.waitKey(1) < 0:
    ret, frame = vc.read()
    frame = cv2.flip(frame,1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    edges = cv2.Canny(blur, 50, 150)

    #find object
    contours, _ = cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

    #draw line on object
    #cv2.drawContours(frame,contours,-1,(0,0,255),3)

    #bounding box (rectangle)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        #count area of object
        area = cv2.contourArea(contour)
        print("Area:", area)

        #perimeter (border length)
        perimeter = cv2.arcLength(contour, True)
        print("Perimeter:", perimeter)

    print("Objects:", len(contours))
    cv2.imshow("Frame", frame)
