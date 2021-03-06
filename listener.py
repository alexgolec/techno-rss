###############################################################################
# initialize the blogs list

# the file is opened with write mode in order to lock out any writers
with open('data/blogs.txt', 'rwa') as f:
    urls = [line.strip().split(' ') for line in f.xreadlines()]

###############################################################################
# methods for handling and merging data

def merge_data(old_data, new_data, key=lambda a:a):
    '''
    Take two lists of items, assume that one is older than the other, and merge
    them in such a way that they form one timeline. The lists are also assumed
    to be sorted.
    '''
    old_cursor = 0
    new_cursor = 0
    ret = []
    while True:
        if old_cursor < len(old_data) and new_cursor < len(new_data):
            old = old_data[old_cursor]
            new = new_data[new_cursor]

            old_key = key(old)
            new_key = key(new)
            if old_key < new_key:
                ret.append(old)
                old_cursor += 1
            elif new_key < old_key:
                ret.append(new)
                new_cursor += 1
            else:
                ret.append(new)
                new_cursor += 1
                old_cursor += 1
        elif old_cursor < len(old_data):
            ret.append(old_data[old_cursor])
            old_cursor += 1
        elif new_cursor < len(new_data):
            ret.append(new_data[new_cursor])
            new_cursor += 1
        else:
            break
    return ret

###############################################################################
# the blog grabber class

import threading
import feedparser
import time
import random
import atexit
import pickle
import copy

from termcolor import colored

def make_blog_filename(url, name):
    return 'url:'+url.replace('/', 'slash')+'-name:'+name

class Blog(threading.Thread):
    def __init__(self, url, name):
        threading.Thread.__init__(self)
        self.url = url
        self.entries = []
        self.last_data = None
        self.name = name

        # fields used for synchronization and CTRL-C interruption support
        self.wake_lock = threading.Condition()
        self.should_kill = False
    def run(self):
        while True:
            self.wake_lock.acquire()
            print 'fetching data'
            data = feedparser.parse(self.url)
            # if there is any new data, perform a merge and save the current
            # data as the last data
            if self.last_data is None or self.data_is_new(data):
                print 'Have new data for', colored(self.name, 'green')
                self.entries = merge_data(self.entries, data['entries'],
                                          key=lambda e: e['published_parsed'])
                self.last_data = data
            self.wake_lock.wait(timeout=60 + random.randint(0, 60))
            if self.should_kill:
                print 'killing thread', colored(self.name, 'blue')
                return
            self.wake_lock.release()
    def kill_now(self):
        '''
        Tell the process that it's time to write data back and die
        '''
        self.wake_lock.acquire()
        self.should_kill = True
        self.wake_lock.notify_all()
        self.wake_lock.release()
    def data_is_new(self, new_data):
        return self.last_data['entries'] != new_data['entries']
    def __getstate__(self):
        return {
            'url':self.url,
            'entries':self.entries,
            'last_data':self.last_data,
            'name':self.name,
        }
    def __setstate__(self, state):
        threading.Thread.__init__(self)
        self.wake_lock = threading.Condition()
        self.should_kill = False

        self.url = state['url']
        self.entries = state['entries']
        self.last_data = state['last_data']
        self.name = state['name']
    def write_back(self):
        filename=make_blog_filename(self.url, self.name)
        # TODO: turn this into a os.path.join
        with open('data/saved_progress/'+filename, 'w') as f:
            pickle.dump(self, f)

import atexit

def get_blog(url, name):
    try:
        with open('data/saved_progress/'+make_blog_filename(url, name)) as f:
            print 'Loading blog thread for', colored(name, 'blue')
            blog = pickle.load(f)
    except IOError:
        print 'Creating new blog thread for', colored(name, 'red')
        blog = Blog(url, name)
    atexit.register(blog.write_back)
    return blog

###############################################################################
# main stuff

if __name__ == '__main__':
    # line format is (url, name)
    blogs = {}
    for item in urls:
        url = item[0]
        name = item[1]
        blog = get_blog(url, name)
        blogs[url] = blog
        blog.start()

    try:
        while True:
            time.sleep(1000)
    except KeyboardInterrupt:
        # the first print swallows the ^C that gets printed on most consoles
        print
        print 'Stopping all threads...'
        for b in blogs:
            blogs[b].kill_now()

    '''
    import descend_json

    old = feedparser.parse(urls[0])
    new = feedparser.parse(urls[0])

    print descend_json.descend_print(feedparser.parse(urls[0]))
    '''
