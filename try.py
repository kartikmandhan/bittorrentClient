import time
import threading
import os
import struct

# # Directory
# directory = "torrents"

# # Parent Directory path
# parent_dir = "./"

# # Path
# path = os.path.join(parent_dir, directory)
# # directoriespath = os.path.dirname(directory)
# print(path)
# print(os.path.dirname(directory))
# print(os.path.exists(os.path.dirname(directory)))
# # os.makedirs(path)
# # print("Directory '% s' created" % directory)
# # f = open("./torrent/a/b/c.txt", "wb+")
# os.makedirs("./kali-linux-2021-3-installer-amd64-iso/2")
# fp = open("new.txt", "rb+")
# fp.seek(2000, 0)
# fp.write(b"\nhello")
# fp.close()


def createBitField(x, data):
    bitfield = b""
    pieceByte = 0
    for i in range(x):
        # 0,1,3
        # 000000000
        if i in data:
            pieceByte = pieceByte | (2 ** 8)
            pieceByte = pieceByte >> 1
        if (i + 1) % 8 == 0:
            bitfield += struct.pack("!B", pieceByte)
            pieceByte = 0
    # adding the last piece's bytes
    if x % 8 != 0:
        bitfield += struct.pack("!B", pieceByte)
    print(bitfield)
    return bitfield


def create_bitfield_message(bitfield_pieces, total_pieces):
    bitfield_payload = b''
    piece_byte = 0
    # check for every torrent piece in bitfield
    for i in range(total_pieces):
        if i in bitfield_pieces:
            piece_byte = piece_byte | (2 ** (7 - (i % 8)))
        if (i + 1) % 8 == 0:
            bitfield_payload += struct.pack("!B", piece_byte)
            piece_byte = 0
    # adding the last piece_bytes
    if total_pieces % 8 != 0:
        bitfield_payload += struct.pack("!B", piece_byte)

    print(bitfield_payload)
    return bitfield_payload


def extractBitField(bitfieldString):
    bitfield = set()
    for i, byte in enumerate(bitfieldString):
        for j in range(8):
            if ((byte >> j) & 1):
                # since we are evaluating each bit from right to left
                pieceNumber = i*8+7-j
                bitfield.add(pieceNumber)
    print(bitfield)


extractBitField(create_bitfield_message([], 10))


StartTime = time.time()


def action():
    print('action ! -> time : {:.1f}s'.format(time.time()-StartTime))


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = threading.Event()
        thread = threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time.time()+self.interval
        while not self.stopEvent.wait(nextTime-time.time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()


# start action every 0.6s
inter = setInterval(0.6, action)
print('just after setInterval -> time : {:.1f}s'.format(time.time()-StartTime))

# will stop interval in 5s
t = threading.Timer(5, inter.cancel)
t.start()
