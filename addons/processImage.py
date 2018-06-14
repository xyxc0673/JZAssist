import os
import time
import requests
from svm import *
from svmutil import *
from PIL import Image


"""
jw_key_color:43
binary_image = binary_img.crop((5, 0, 53, 25))
"""

"""
lib_key_color:1
binary_image = binary_img.crop((3, 14, 52, 28))
"""

key_color = {
    "jw": 43,
    "lib": 0,
    "card": 47
}

crop_xy = {
    "jw": (5, 0, 53, 25),
    "lib": (3, 14, 52, 28),
    "card": (20, 4, 80, 23)
}


class ProcessImage:
    working_key = ""
    feature_path = ""
    model_path = ""
    answer_path = ""
    train_path = ""

    def set_working_key(self, key):
        running_path = os.path.dirname(__file__)
        working_dir = "/process_image/%s/" % key
        self.working_key = key
        self.feature_path = os.path.join(running_path + working_dir + "pix_feature.txt")
        self.model_path = os.path.join(running_path + working_dir + "model.txt")
        self.answer_path = os.path.join(running_path + working_dir + "answer.txt")
        self.train_path = os.path.join(running_path + working_dir + "trains")

    def pixel_sort(self, img):
        img = Image.open(img)
        his = img.histogram()
        values = {}

        for i in range(256):
            values[i] = his[i]

        for j, k in sorted(values.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(j, k)

    def binaryzation(self, img):
        """

        :param img:
        :return new_img:
        """
        img.convert("L")
        new_img = Image.new("L", img.size, 255)

        for x in range(img.size[0]):
            for y in range(img.size[1]):
                pix = img.getpixel((x, y))
                if type(pix) == tuple:
                    pix = pix[0]
                if pix == key_color[self.working_key]:
                    new_img.putpixel((x, y), 0)

        return new_img

    def split(self, img):
        """
        split the img to four equal width and height img
        :param img:
        :return img_slices:
        """
        binary_img = self.binaryzation(img)
        binary_image = binary_img.crop(crop_xy[self.working_key])
        width = binary_image.size[0] / 4
        img_slices = []

        for i in range(0, 4):
            tmp_img = binary_image.crop((width * i, 0, width * (i + 1), binary_image.size[1]))
            img_slices.append(tmp_img)

        return img_slices

    def get_feature(self, img, output=False):
        """

        :param img:
        :param output:
        :return:
        """
        width, height = img.size
        pix_cnt_list = []

        for x in range(width):
            pix_cnt_x = 0
            for y in range(height):
                if img.getpixel((x, y)) == 0:
                    pix_cnt_x += 1
            pix_cnt_list.append(pix_cnt_x)

        for y in range(height):
            pix_cnt_y = 0
            for x in range(width):
                if img.getpixel((x, y)) == 0:
                    pix_cnt_y += 1
            pix_cnt_list.append(pix_cnt_y)

        if output:
            tmp_list = []
            for i in range(len(pix_cnt_list)):
                tmp_str = "%s:%s" % (i, pix_cnt_list[i])
                tmp_list.append(tmp_str)

            mode_line = " ".join(tmp_list)
            return mode_line
        else:
            x = {}
            for i in range(len(pix_cnt_list)):
                x[i] = float(pix_cnt_list[i])
            return x

    def train_single_img(self):
        dir_list = sorted(os.listdir(self.train_path))
        mode_line_list = []

        for letter in dir_list:
            single_img_path = "%s/%s/" % (self.train_path, letter)
            img_file_list = os.listdir(single_img_path)
            for file in img_file_list:
                img = Image.open(single_img_path+file)
                feature = self.get_feature(img, output=True)
                tmp_str = "%s %s" % (ord(letter), feature)
                mode_line_list.append(tmp_str)

        mode_text = "\n".join(mode_line_list)
        with open(self.feature_path, "w") as f:
            f.write(mode_text)

    def train_svm_model(self):

        y, x = svm_read_problem(self.feature_path)
        model = svm_train(y, x)
        svm_save_model(self.model_path, model)

    def predict(self, f):

        img = Image.open(f)
        img_slices = self.split(img)
        model = svm_load_model(self.model_path)
        y = [float(i) for i in range(0, 4)]
        x = []
        for tmp_img in img_slices:
            x.append(self.get_feature(tmp_img))

        p_label, p_acc, p_val = svm_predict(y, x, model)
        guess = []
        for label in p_label:
            guess.append(chr(int(label)))

        return guess


process = ProcessImage()

if __name__ == "__main__":
    working_key = "card"
    working_dir = "process_image/%s/" % working_key
    temp_path = working_dir + "temp"
    sample_path = working_dir + "samples"
    train_path = working_dir + "trains"

    process = ProcessImage()
    # process.train_single_img()
    # process.train_svm_model()

    captcha_url = {
        "jw": "http://125.89.69.234/CheckCode.aspx",
        "lib": "http://opac.jluzh.com/reader/captcha.php?",
        "card": "https://icard.jluzh.com/check.action"
    }

    def download_images(url, start, end, for_samples=False):
        if for_samples:
            real_path = sample_path
        else:
            real_path = temp_path

        for i in range(start, end):
            #time.sleep(1)
            print("downloading %s.png..." % i)
            r = requests.get(url)
            with open("%s/%s.png" % (real_path, i), "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

    def file_sort(x):
        return int(x.split(".")[0])

    def save_single_img():

        labels = get_labels()
        print(labels)
        dir_list = sorted(os.listdir(sample_path), key=lambda x: int(x.split(".")[0]))

        for i1 in range(len(dir_list)):
            with open("%s/%s" % (sample_path, dir_list[i1]), "rb") as f:
                img = Image.open(f)
                img_slices = process.split(img)
            for i2 in range(len(img_slices)):
                img_slices[i2].save("%s/%s/%s_%s.png" % (train_path, labels[i1][i2], dir_list[i1].split(".")[0], i2))

    def get_labels():

        with open(process.answer_path, "r") as f:
            tmp_str = f.read()
        labels = tmp_str.split("\n")

        return labels

    def ocr():
        dir_list = sorted(os.listdir(temp_path))

        for img in dir_list:
            print("%s/%s" % (temp_path, img))
            with open("%s/%s" % (temp_path, img), "rb") as f:
                guess = process.predict(f)
            print("%s %s" % (img, guess))

    def get_single_split():
        tmp_path = working_dir + "temp"
        with open("%s/%s" % (tmp_path, "0.png"), "rb") as f:
            img = Image.open(f)
            img_slices = process.split(img)
            for i in range(len(img_slices)):
                img_slices[i].save(working_dir+"%s.png" % i)

    process.set_working_key(working_key)
    #process.train_single_img()
    #process.train_svm_model()

    #get_single_split()

    #process.pixel_sort(working_dir+"temp/0.png")

    #process.train_single_img()
    #process.train_svm_model()
    #get_labels()
    #download_images(captcha_url[working_key], 0, 100)
    # with open("temp/lib/0.png", "rb") as f:
    #     img = Image.open(f)
    #     process.pixel_sort(img)
    #save_single_img()
    #ocr()

