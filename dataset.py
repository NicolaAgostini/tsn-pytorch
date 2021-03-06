import torch.utils.data as data

from PIL import Image
import os
import os.path
import numpy as np
from numpy.random import randint
import re
from gaze_io_sample import *

class VideoRecord(object):
    def __init__(self, row):
        self._data = row
        #print(self._data)

    @property
    def path(self):
        return self._data[0]+"-"+self._data[1]+"-"+self._data[2]

    @property
    #def num_frames(self):
    def num_frames(self):  # total number of frames in the action
        #print(int(((int(self._data[4])/1000)*30)-((int(self._data[3])/1000)*30)))
        return round(((int(self._data[4])/1000)*30)-((int(self._data[3])/1000)*30))  # end frame - start frame

    @property
    def label(self):
        return int(self._data[7])-1

    @property
    def start_fr(self):  # start time in frame
        return round((int(self._data[3])/1000)*30)  # in frames number



class TSNDataSet(data.Dataset):
    def __init__(self, root_path, list_file,
                 num_segments=3, new_length=1, modality='RGB',
                 image_tmpl="frame_{:010d}.jpg", transform=None,
                 force_grayscale=False, random_shift=True, test_mode=False):

        self.root_path = root_path
        self.list_file = list_file
        self.num_segments = num_segments
        self.new_length = new_length
        self.modality = modality
        self.image_tmpl = image_tmpl
        self.transform = transform
        self.random_shift = random_shift
        self.test_mode = test_mode

        if self.modality == 'RGBDiff':
            self.new_length += 1# Diff needs one more image to calculate diff

        self._parse_list()

    def _load_image(self, directory, idx):
        if self.modality == 'RGB' or self.modality == 'RGBDiff':

            img = Image.open(os.path.join("/home/2/2014/nagostin/Desktop/frames/"+directory, directory + "_" +self.image_tmpl.format(idx))).convert('RGB')
            gaze_center_x, gaze_center_y = return_gaze_point(idx,directory)  # sono normalizzati sulla grandezza dell'immagine
            width, height = img.size
            raggio = 80
            pix = np.array(img)
            gaze_center_x, gaze_center_y = gaze_center_x * width, gaze_center_y*height
            x = return_cropped_img(pix, gaze_center_x, gaze_center_y, height, width, raggio,"soft")

            im = Image.fromarray(np.uint8(x))  # to convert back to img pil
            
            return [im]

            #return [Image.open(os.path.join("/home/2/2014/nagostin/Desktop/frames/"+directory, directory + "_" +self.image_tmpl.format(idx))).convert('RGB')]

        elif self.modality == 'Flow':
            x_img = Image.open(os.path.join(directory, self.image_tmpl.format('x', idx))).convert('L')
            y_img = Image.open(os.path.join(directory, self.image_tmpl.format('y', idx))).convert('L')

            return [x_img, y_img]

    def _parse_list(self):
        self.video_list = [VideoRecord(x.replace("-"," ").split(" ")) for x in open(self.list_file)]  # give in input train_split1.txt and tes_split1.txt

    def _sample_indices(self, record):
        """

        :param record: VideoRecord
        :return: list
        """

        average_duration = (record.num_frames - self.new_length + 1) // self.num_segments
        if average_duration > 0:
            offsets = np.multiply(list(range(self.num_segments)), average_duration) + randint(average_duration, size=self.num_segments)
        elif record.num_frames > self.num_segments:
            offsets = np.sort(randint(record.num_frames - self.new_length + 1, size=self.num_segments))
        else:
            offsets = np.zeros((self.num_segments,))
        #print(record.path + " " + str(record.start_fr) + "  " + str(offsets)+ "  "+ str(record.label)+ str(offsets+record.start_fr))
        offsets = offsets+record.start_fr  # i want the frames number at 30 fps

        return offsets + 1

    def _get_val_indices(self, record):
        if record.num_frames > self.num_segments + self.new_length - 1:
            tick = (record.num_frames - self.new_length + 1) / float(self.num_segments)
            offsets = np.array([int(tick / 2.0 + tick * x) for x in range(self.num_segments)])
        else:
            offsets = np.zeros((self.num_segments,))
        offsets = offsets + record.start_fr
        return offsets + 1

    def _get_test_indices(self, record):  # TODO fixme  like val and train indices ( offsets = offsets + record.start_fr)

        tick = (record.num_frames - self.new_length + 1) / float(self.num_segments)

        offsets = np.array([int(tick / 2.0 + tick * x) for x in range(self.num_segments)])

        return offsets + 1

    def __getitem__(self, index):
        record = self.video_list[index]

        if not self.test_mode:
            segment_indices = self._sample_indices(record) if self.random_shift else self._get_val_indices(record)
        else:
            segment_indices = self._get_test_indices(record)

        return self.get(record, segment_indices)

    def get(self, record, indices):

        images = list()
        for seg_ind in indices:  # indices = [30,60,90]
            p = int(seg_ind)
            for i in range(self.new_length):
                seg_imgs = self._load_image(record.path, p)
                images.extend(seg_imgs)
                if p < record.num_frames:
                    p += 1

        process_data = self.transform(images)
        return process_data, record.label

    def __len__(self):
        return len(self.video_list)
