from PIL import Image
import math
import os
import requests
import hashlib
# from addons.utils import fn_timer, init_mongodb
import random
import time
import pickle


class VectorCompare:
    #计算矢量大小
    def magnitude(self, concordance):
        total = 0
        for word, count in concordance.items():
            total += count ** 2
        return math.sqrt(total)

    #计算矢量之间的 cos 值
    def relation(self, concordance1, concordance2):
        relevance = 0
        topvalue = 0
        for word, count in concordance1.items():
            if word in concordance2:
                topvalue += count * concordance2[word]
        return topvalue / (self.magnitude(concordance1) * self.magnitude(concordance2))


class Crack:

    def download_images(self, url, start, end):

        for i in range(start, end):
            r = requests.get(url)
            print(i)
            with open("temp/%s.png" % i, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

    def train_data(self, auto):

        dir_list = os.listdir("./temp/")
        for m in range(0, len(dir_list)):
            img_num = dir_list[m].split(".")[0]

            if auto:
                guesses, image_slices = self.compare("./temp/%s"%dir_list[m], True)
                print("%s recognition process finishes, the result is %s" % (dir_list[m], guesses))
            else:
                image_slices = self._slice(dir_list[m])

            for n in range(0, len(image_slices)):
                if not auto:
                    image_slices[n].save("./train/%s_%s.png" % (img_num, n))
                    i = input("%s_%s.png looks like : " % (img_num, n))
                    if i != "":
                        image_slices[n].save("./train/%s/%s_%s.png" % (i, img_num, n))
                else:
                    image_slices[n].save("./train/%s/%s_%s.png" % (guesses[n], img_num, n))

            os.remove("./temp/%s"%dir_list[m])

    def train_data2(self, auto):
        dir_list = os.listdir("./temp/")
        for file in dir_list:
            if auto:
                guesses, image_slices = self.compare("./temp/%s" % file, True)
            else:
                image_slices = self._slice2("./temp/%s" % file)
            if len(image_slices) == 4:
                m = hashlib.md5()
                for i in range(0, 4):
                    strs = "%s%s" % (time.time(), i)
                    m.update(strs.encode('utf-8'))
                    prefix = file.split(".")[0]
                    image_slices[i].save("./test/deepin_%s_%s.png" % (prefix, i))
                    # if auto:
                    #     letter = guesses[i]
                    # else:
                    #     letter = file.split(".")[0][i]
                    # image_slices[i].save("./train/%s/%s.png" % (letter, m.hexdigest()))

    def save_to_mongodb(self):
        image_set = self._load_image_set()
        db = init_mongodb()
        trains = db["trains"]
        m = hashlib.md5()
        train_list = []

        for i in image_set:
            for x, y in i.items():
                strs = str(time.time())
                m.update(strs.encode("utf-8"))
                name = "%s_%s" % (x, m.hexdigest())
                pickled_vector = pickle.dumps(y)
                train_list.append({"letter": name, "vector": pickled_vector})

        trains.insert(train_list)

    def _binaryzation(self, im, io):
        if not io:
            with open(im, "rb") as f:
                image = Image.open(f)
                image.convert("P")
        else:
            image = Image.open(im)
            image.convert("P")

        img = Image.new("P", image.size, 255)

        for x in range(image.size[0]):
            for y in range(image.size[1]):
                pix = image.getpixel((x, y))
                if pix == 43:
                    img.putpixel((x, y), 0)

        return img

    # @fn_timer
    def compare(self, im="code.png", io=False, train=False):

        binary_image = self._binaryzation(im, io)
        image_slices = self._slice2(binary_image)
        trains = self._load_trains_from_mongodb()

        vector = VectorCompare()

        guesses = []

        for img in image_slices:
            guess = []
            for image in trains:
                x = image["letter"]
                y = image["vector"]
                if len(y) != 0:
                    guess.append((vector.relation(y[0], self._bulid_vector(img)), x))

            guess.sort(reverse=True)
            guesses.append(guess[0][1])

        if train:
            return guesses, image_slices
        return guesses

    # @fn_timer
    def compare1(self, im="code.png", io=False, train=False):

        binary_image = self._binaryzation(im, io)
        image_slices = self._slice2(binary_image)
        image_set = self._load_image_set()
        vector = VectorCompare()
        guesses = []

        for img in image_slices:
            guess = []
            for image in image_set:
                for x, y in image.items():
                    if len(y) != 0:
                        guess.append((vector.relation(y[0], self._bulid_vector(img)), x))

            guess.sort(reverse=True)
            guesses.append(guess[0][1])

        if train:
            return guesses, image_slices
        return guesses

    # @fn_timer
    def compare2(self, add="code.png", train=False):

        image_slices = self._slice2(add)
        image_set = self._load_image_set()
        guesses = []
        for img in image_slices:
            width = img.size[0]
            height = img.size[1]
            min = width*height
            guess = []
            for image in image_set:
                count = 0
                if abs(width - image[1][0].size[0]) > 2:
                    continue
                min_width = width < image[1][0].size[0] and width or image[1][0].size[0]
                min_height = height < image[1][0].size[1] and height or image[1][0].size[1]
                for x in range(min_width):
                    for y in range(min_height):
                        if img.getpixel((x, y)) != image[1][0].getpixel((x, y)):
                            count += 1
                guess.append((count, image[0]))
            guess.sort()

            guesses.append(guess[0][1])

        return guesses

    def _slice(self, add):
        binary_image = self._binaryzation(add)
        in_letter = False
        found_letter = False
        start = 0
        end = 0
        letters = []

        for y in range(binary_image.size[0]):
            for x in range(binary_image.size[1]):

                pix = binary_image.getpixel((y, x))
                if pix != 255:
                    in_letter = True

            if found_letter == False and in_letter == True:
                found_letter = True
                start = y

            if found_letter == True and in_letter == False:
                found_letter = False
                end = y
                if end-start > 1:
                    letters.append((start, end))

            in_letter = False

        image_slices = []
        for letter in letters:
            width = letter[1] - letter[0]
            num = round(width/12)

            if num > 1:
                width = width/num
                for i in range(0, num):
                    img = binary_image.crop((letter[0]+width*i, 0, letter[0]+width*(i+1), binary_image.size[1]))
                    image_slices.append(img)
            else:
                img = binary_image.crop((letter[0], 0, letter[1], binary_image.size[1]))
                image_slices.append(img)

        return image_slices

    def _slice2(self, image):
        binary_image = self._binaryzation(image,io=False)
        binary_image = binary_image.crop((5, 0, 53, 25))
        width = binary_image.size[0]/4
        image_slices = []

        for i in range(0, 4):
            img = binary_image.crop((width*i, 0, width*(i+1), binary_image.size[1]))
            image_slices.append(img)

        return image_slices

    def _bulid_vector(self, image):
        d1 = {}
        data = image.getdata()

        for i in range(0, len(data)):
            d1[i] = data[i]

        return d1

    def _load_image_set(self):
        iconset = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i',
                   'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y']
        image_set = []

        for letter in iconset:
            for img in os.listdir('addons/train/%s/' % letter):
                temp = []
                if img != 'Thumbs.db' and img != ".DS_Store":
                    # temp.append(self._bulid_vector(Image.open("./train/%s/%s" % (letter, img))))
                    temp.append(self._bulid_vector(Image.open("addons/train/%s/%s" % (letter, img))))
                if len(temp) != 0:
                    image_set.append({letter: temp})

        return image_set

    def _load_trains_from_mongodb(self):
        db = init_mongodb()
        trains_collection = db["trains"].find()
        trains = []

        for doc in trains_collection:
            x = doc["letter"].split("_")[0]
            y = pickle.loads(doc["vector"])
            trains.append({"letter": x, "vector": y})

        return trains

crack = Crack()

if __name__ == "__main__":

    crack = Crack()
    #crack.save_to_mongodb()

    def train(auto, download_new_images, url, start=-1, end=-1):
        if download_new_images and url:
                if start != -1 and end != -1 and end > start:
                    crack.download_images(url, start, end)
        crack.train_data2(auto)

    # @fn_timer
    def ocr():
        for img in os.listdir("./temp2/"):
            guesses = crack.compare("./temp2/%s" % img)
            print("%s %s" % (img, guesses))

    url = "http://125.89.69.234/CheckCode.aspx"
    #train(False, False, url, 0, 100)
    temp_path = "temp/"
    test_path = "test"
    for i in os.listdir(temp_path):
    	prefix = i.split(".")[0]
    	img = crack._binaryzation(temp_path+i, io=False)
    	img.save("%s/deepin_%s.png" % (test_path, prefix))
