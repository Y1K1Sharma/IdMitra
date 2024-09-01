from pytesseract import Output
import cv2
import numpy as np
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

class Masker:
    def __init__(self, source_file):  # Corrected from _init_ to __init__
        self.image = self.process_image(source_file)
        self.image_data = self.get_image_data()
    
    def process_image(self, source_file):
        contents = source_file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    
    def get_image_data(self):
        rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        res = pytesseract.image_to_data(rgb, output_type=Output.DICT)
        return res

    def check_aadhar_num(self, text):
        return len(text) == 4 and text.isdigit()

    def get_uid_details(self):
        text_data = self.image_data['text']
        uid = []
        for i in range(len(text_data)):
            if self.check_aadhar_num(text_data[i]):
                if len(text_data) < i + 2:
                    return (False, None)
                if self.check_aadhar_num(text_data[i + 1]) and self.check_aadhar_num(text_data[i + 2]):
                    uid.extend((i, i+1, i+2))
                    break
        
        if len(uid) != 3:
            return False, None
        else:
            return True, uid

    def mask_aadhar(self):
        success, uid = self.get_uid_details()

        if success:
            self.mask_uid_number(uid)
            return True
        else:
            return False
    
    def mask_uid_number(self, aadhar_data):
        for i in range(len(aadhar_data)):
            if i == 2:
                break
            d = aadhar_data[i]
            x = self.image_data['left'][d]
            y = self.image_data['top'][d]
            w = self.image_data['width'][d]
            h = self.image_data['height'][d]
                                    
            cv2.rectangle(self.image, (x, y), (x + w, y + h), (0, 0, 0), -1)

    def mask_faces(self):
        # Detect faces
        faces = face_cascade.detectMultiScale(self.image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        # Mask faces
        for (x, y, w, h) in faces:
            cv2.rectangle(self.image, (x, y), (x + w, y + h), (0, 0, 0), -1)
    
    def mask_all(self, output_file):
        # Mask Aadhaar number
        self.mask_aadhar()
        
        # Mask faces
        self.mask_faces()

        # Save the output image
        cv2.imwrite(output_file.name, self.image)

if __name__ == "__main__":
    with open("1.jpg", "rb") as source_file, open("qw.jpg", "wb") as output_file:
        masker = Masker(source_file)
        masker.mask_all(output_file)

    print("Aadhaar number and faces masked successfully!")
