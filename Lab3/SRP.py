import enum
import random
import time


class MessageStatus(enum.Enum):
    OK = enum.auto()
    LOST = enum.auto()


class Message:
    number = -1
    real_number = -1
    data = ""
    status = MessageStatus.OK

    def __init__(self):
        pass

    def copy(self):
        msg = Message()
        msg.number = self.number
        msg.data = self.data
        msg.status = self.status

    def __str__(self):
        return f"({self.real_number}({self.number}), {self.data}, {self.status})"


class MsgQueue:
    def __init__(self, loss_probability=0.0):
        self.msg_queue = []
        self.loss_probability = loss_probability
        pass

    def has_msg(self):
        if len(self.msg_queue) <= 0:
            return False
        else:
            return True

    def get_message(self):
        if self.has_msg():
            result = self.msg_queue[0]
            self.msg_queue.pop(0)
            return result

    def send_message(self, msg):
        tmp_msg = self.emulating_channel_problems(msg)
        self.msg_queue.append(tmp_msg)

    def emulating_channel_problems(self, msg):
        val = random.random()
        if val <= self.loss_probability:
            msg.status = MessageStatus.LOST

        return msg

    def __str__(self):
        res_str = "[ "
        for i in range(len(self.msg_queue)):
            msg = self.msg_queue[i]
            res_str += f"({msg.number}, {msg.status}), "

        res_str += "]"
        return res_str


class WndMsgStatus(enum.Enum):
    BUSY = enum.auto()
    NEED_REPEAT = enum.auto()
    CAN_BE_USED = enum.auto()


class WndNode:
    def __init__(self, number):
        self.status = WndMsgStatus.NEED_REPEAT
        self.time = 0
        self.number = number
        pass

    def __str__(self):
        return f"( {self.number}, {self.status}, {self.time})"


class SRPSender:
    def __init__(self, window_size = 16, max_number = 1024, timeout = 0.2):
        self.window_size = window_size
        self.max_number = max_number
        self.timeout = timeout
        self.wnd_nodes = [WndNode(i) for i in range(window_size)]
        self.ans_count = 0
        self.send_msg_queue = MsgQueue()
        self.recieve_msg_queue = MsgQueue()
        self.finished = False

    def isDone(self):
        return self.ans_count >= self.max_number

    def update(self):
        if self.isDone():
            if not self.finished:
                self.finish()
            return

        if self.recieve_msg_queue.has_msg():
            ans = self.recieve_msg_queue.get_message()
            self.ans_count += 1
            self.wnd_nodes[ans.number].status = WndMsgStatus.CAN_BE_USED

        # долго нет ответа с последнего подтверждения
        curr_time = time.time()
        for i in range(self.window_size):
            if self.wnd_nodes[i].number > self.max_number:
                continue

            send_time = self.wnd_nodes[i].time
            if curr_time - send_time > self.timeout:
                # произошёл сбой, нужно повторить отправку этого сообщения
                self.wnd_nodes[i].status = WndMsgStatus.NEED_REPEAT

        # отправляем новые или повторяем, если необходимо
        for i in range(self.window_size):
            if self.wnd_nodes[i].number > self.max_number:
                continue

            if self.wnd_nodes[i].status == WndMsgStatus.BUSY:
                continue

            elif self.wnd_nodes[i].status == WndMsgStatus.NEED_REPEAT:
                self.wnd_nodes[i].status = WndMsgStatus.BUSY
                self.wnd_nodes[i].time = time.time()

                msg = Message()
                msg.number = i
                msg.real_number = self.wnd_nodes[i].number
                self.send_msg_queue.send_message(msg)

            elif self.wnd_nodes[i].status == WndMsgStatus.CAN_BE_USED:
                self.wnd_nodes[i].status = WndMsgStatus.BUSY
                self.wnd_nodes[i].time = time.time()
                self.wnd_nodes[i].number = self.wnd_nodes[i].number + self.window_size

                if self.wnd_nodes[i].number > self.max_number:
                    continue

                msg = Message()
                msg.number = i
                msg.real_number = self.wnd_nodes[i].number
                self.send_msg_queue.send_message(msg)

    def finish(self):
        msg = Message()
        msg.data = "STOP"
        self.send_msg_queue.send_message(msg)
        self.finished = True


class SRPReceiver:
    def __init__(self, window_size = 16):
        self.window_size = window_size
        self.finished = False
        self.send_msg_queue = MsgQueue()
        self.recieve_msg_queue = MsgQueue()

    def isDone(self):
        return self.finished

    def update(self):
        if self.recieve_msg_queue.has_msg():
            curr_msg = self.recieve_msg_queue.get_message()

            if curr_msg.data == "STOP":
                self.finished = True
                return

            if curr_msg.status == MessageStatus.LOST:
                return

            ans = Message()
            ans.number = curr_msg.number
            self.send_msg_queue.send_message(ans)
