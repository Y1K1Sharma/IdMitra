## Usage
### Installing dependencies
1. Install all dependencies via `pip install -r requirements.txt`.
2. Install the Tesseract helper locally via `sudo apt install tesseract-ocr -y` on Ubuntu or `sudo pacman -Syu tesseract` on Arch Linux.
3. Install Spacy language definitions locally via `python -m spacy download en_core_web_sm`.

Once you've installed the above, you're all set.

### Running

To run IdMitr, type:

```
python3 IdMitr.py <location to scan>
```
_where `<location to scan>` is a file or a directory._

Octopii currently supports local scanning via filesystem path, S3 URLs and Apache open directory listings. You can also provide individual image URLs or files as an argument.


```

A file named `output.txt` is created, containing output from the tool. This file is appended to sequentially in real-time.

## Working

IdMitr uses Tesseract for Optical Character Recognition (OCR) and NLTK for Natural Language Processing (NLP) to detect for strings of personal identifiable information. This is done via the following steps:

### 1. Input and importing 

IdMitr scans for images (jpg and png) and documents (pdf, doc, txt etc). It supports 3 sources:

1. Amazon Simple Storage Service (S3): traverses the XML from S3 container URLs
2. Open directory listing: traverses Apache open directory listings and scans for files 
3. Local filesystem: can access files and folders within UNIX-like filesystems (macOS and Linux-based operating systems)

Images are detected via Python Imaging Library (PIL) and are opened with OpenCV. PDFs are converted into a list of images and are scanned via OCR. Text-based file types are read into strings and are scanned without OCR.

### 2. Face detection

A binary classification image detection technique - known as a "Haar cascade" - is used to detect faces within images. A pre-trained cascade model is supplied in this repo, which contains cascade data for OpenCV to use. Multiple faces can be detected within the same PII image, and the number of faces detected is returned.

### 3. Cleaning image and reading text

Images are then "cleaned" for text extraction with the following image transformation steps:

1. Auto-rotation
2. Grayscaling
3. Monochrome
4. Mean threshold
5. Gaussian threshold
6. 3x Deskewing

![Image filtering illustration](image_filtering_illustration.png) 

Since these steps strip away image data (including colors in photographs), this image cleaning process occurs after attempting face detection. 

### 4. Optical Character Recognition (OCR)

Tesseract is used to grab all text strings from an image/file. It is then tokenized into a list of strings, split by newline characters ('\n') and spaces (' '). Garbled text, such as `null` strings and single characters are discarded from this list, resulting in an 'intelligible' list of potential words.

This list of words is then fed into a similarity checker function. This function uses Gestalt pattern matching to compare each word extracted from the PII document with a list of keywords, present in `definitions.json`. This check happens once per cleaning. The number of times a word occurs from the keywords list is counted and this is used to derive a confidence score. When a particular definition's keywords appear repeatedly in these scans, that definition gets the highest score and is picked as the predicted PII class.

IdMitr also checks for sensitive PII substrings such as emails, phone numbers and common government ID unique identifiers using regular expressions. It can also extract geolocation data such as addresses and countries using Natural Language Processing.

### 4. Output

The output consists of the following:
- `file_path`: Where the file containing PII can be found
- `pii_class`: The type of PII this file contains
- `country_of_origin`: Where this PII originates from. 
- `identifiers`: Unique identifiers, codes or numbers that may be used to target the individual mentioned in the PII.
- `emails` and `phone_numbers`: Contact information in the file.
- `addresses`: Any form of geolocation data in the PII. This may be used to triangulate an individual's location.
