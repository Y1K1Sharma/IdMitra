#importing necessary libraries
from pytesseract import Output
import cv2
import numpy as np
import pytesseract
import json, textract, sys, urllib, os, shutil, traceback
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from pdf2image import convert_from_path
import image_utils, file_utils, text_utils, webhook
import tempfile

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

output_file = "output.json"
notifyURL = ""
temp_dir = ".OCTOPII_TEMP/"

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
        faces = face_cascade.detectMultiScale(self.image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        for (x, y, w, h) in faces:
            cv2.rectangle(self.image, (x, y), (x + w, y + h), (0, 0, 0), -1)
    
    def mask_all(self, output_file):
        self.mask_aadhar()
        self.mask_faces()
        cv2.imwrite(output_file.name, self.image)

def help_screen():
    help = '''Usage: python idmitra.py <file, local path or URL>
Note: Only Unix-like filesystems, S3 and open directory URLs are supported.'''
    print(help)

def search_pii(file_path):
    contains_faces = 0
    intelligible = None

    if file_utils.is_image(file_path):
        filename = os.path.basename(file_path)
        output_filename = "masked_" + filename
        temp_output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg', dir=os.path.dirname(file_path))
        temp_output_filepath = temp_output_file.name
        
        with open(file_path, "rb") as source_file:
            masker = Masker(source_file)
            
            contains_faces = masker.mask_all(temp_output_file)
            temp_output_file.close()
            
            output_filepath = os.path.join(os.path.dirname(file_path), output_filename)
            shutil.move(temp_output_filepath, output_filepath)
        
        image = cv2.imread(output_filepath)
        text = pytesseract.image_to_string(image)
        
    elif file_utils.is_pdf(file_path):
        pdf_pages = convert_from_path(file_path, 400)
        text = ""
        for page in pdf_pages:
            contains_faces += image_utils.scan_image_for_people(page)
            text += pytesseract.image_to_string(page)

    else:
        text = textract.process(file_path).decode()
        intelligible = text_utils.string_tokenizer(text)

    addresses = text_utils.regional_pii(text)
    emails = text_utils.email_pii(text, rules)
    phone_numbers = text_utils.phone_pii(text, rules)

    if intelligible is None:
        intelligible = {}

    keywords_scores = text_utils.keywords_classify_pii(rules, intelligible)
    score = max(keywords_scores.values(), default=0)
    pii_class = list(keywords_scores.keys())[list(keywords_scores.values()).index(score)] if keywords_scores else None

    country_of_origin = rules.get(pii_class, {}).get("region", "Unknown")
    identifiers = text_utils.id_card_numbers_pii(text, rules)

    if score < 5:
        pii_class = None

    if identifiers:
        identifiers = identifiers[0]["result"]

    if temp_dir in file_path:
        file_path = file_path.replace(temp_dir, "")
        file_path = urllib.parse.unquote(file_path)

    result = {
        "file_path": file_path,
        "pii_class": pii_class,
        "score": score,
        "country_of_origin": country_of_origin,
        "faces": contains_faces,
        "identifiers": identifiers,
        "emails": emails,
        "phone_numbers": phone_numbers,
        "addresses": addresses
    }

    return result



if __name__ in '__main__':
    if len(sys.argv) == 1:
        help_screen()
        exit(-1)
    else:
        location = sys.argv[1]

        notify_index = sys.argv.index('--notify') if '--notify' in sys.argv else -1
        if notify_index != -1 and notify_index + 1 < len(sys.argv): notifyURL = sys.argv[notify_index + 1]
        else: notifyURL = None

    rules = text_utils.get_regexes()

    files = []
    temp_exists = False

    print("Scanning '" + location + "'")

    try:
        shutil.rmtree(temp_dir)
    except: pass

    if "http" in location:
        try:
            file_urls = []
            _, extension = os.path.splitext(location)
            if extension != "":
                file_urls.append(location)
            else:
                files = file_utils.list_local_files(location)

            file_urls = file_utils.list_s3_files(location)
            if len(file_urls) != 0:
                temp_exists = True
                os.makedirs(os.path.dirname(temp_dir))
                for url in file_urls:
                    file_name = urllib.parse.quote(url, "UTF-8")
                    urllib.request.urlretrieve(url, temp_dir + file_name)

        except:
            try:
                file_urls = file_utils.list_directory_files(location)
                if len(file_urls) != 0:
                    temp_exists = True
                    os.makedirs(os.path.dirname(temp_dir))
                    for url in file_urls:
                        try:
                            encoded_url = urllib.parse.quote(url, "UTF-8")
                            urllib.request.urlretrieve(url, temp_dir + encoded_url)
                        except: pass

                else:
                    temp_exists = True
                    os.makedirs(os.path.dirname(temp_dir))
                    encoded_url = urllib.parse.quote(location, "UTF-8") + ".txt"
                    urllib.request.urlretrieve(location, temp_dir + encoded_url)

            except:
                traceback.print_exc()
                print("This URL is not a valid S3 or has no directory listing enabled. Try running Octopii on these files locally.")
                sys.exit(-1)

        files = file_utils.list_local_files(temp_dir)
    else:
        _, extension = os.path.splitext(location)
        if extension != "":
            files.append(location)
        else:
            files = file_utils.list_local_files(location)

    if len(files) == 0:
        print("Invalid path provided. Please provide a non-empty directory or a file as an argument.")
        sys.exit(0)

    for file_path in files:
        try:
            results = search_pii(file_path)
            print(json.dumps(results, indent=4))
            file_utils.append_to_output_file(results, output_file)
            if notifyURL != None: webhook.push_data(json.dumps(results), notifyURL)
            print("\nOutput saved in " + output_file)

        except textract.exceptions.MissingFileError:
            print("\nCouldn't find file '" + file_path + "', skipping...")

        except textract.exceptions.ShellError:
            print("\nFile '" + file_path + "' is empty or corrupt, skipping...")

    if temp_exists: shutil.rmtree(temp_dir)

    sys.exit(0)
