import numpy as np
import enum
import time
from multiprocessing import Process, Event, Queue, Value
from queue import Empty
import matplotlib.pyplot as plt
import matplotlib
import ctypes

matplotlib.use('TkAgg')

class MessageState(enum.Enum):
    PENDING = enum.auto()
    SENT = enum.auto()
    RECEIVED = enum.auto()
    CONFIRMED = enum.auto()

class MessageType(enum.Enum):
    DATA = enum.auto()
    CONFORMATION = enum.auto()
    END = enum.auto()

class Message:
    def __init__(self, type : MessageType, index : int, payload = None) -> None:
        self.type = type
        self.index = index
        self.payload = payload

class FlyingMessage:
    def __init__(self, message : Message, start_time_ns : int) -> None:
        self.message = message
        self.start_time_ns = start_time_ns

class OneWayChanel:
    def __init__(self, time_to_pass_ns : int, loss_probability, rand) -> None:
        self.input_queue = Queue()
        self.flying_queue = Queue()
        self.output_queue = Queue()
        self.rand = rand
        self.time_to_pass_ns = time_to_pass_ns
        self.loss_probability = loss_probability
        self.flying_message = None
        self.put = self.input_queue.put
        self.get = self.output_queue.get

    def process_input(self) -> None:
        try:
            while True:
                new_message = self.input_queue.get_nowait()
                self.flying_queue.put(FlyingMessage(new_message, time.time_ns()))
        except Empty:
            pass

    def process_output(self) -> None:
        while True:
            try:
                if self.flying_message is None:
                    self.flying_message = self.flying_queue.get_nowait()
            except Empty:
                break
            if time.time_ns() < self.flying_message.start_time_ns + self.time_to_pass_ns:
                break
            if self.rand() > self.loss_probability:
                self.output_queue.put(self.flying_message.message)
            self.flying_message = None
    
    def process(self) -> None:
        self.process_input()
        self.process_output()

def repeat_until(work, stop) -> None:
    while(not stop.is_set()):
        work()


class GoBackN:
    def name():
        return 'GoBackN'

    def move_window(prev_pos, message_states) -> int:
        for pos in range(prev_pos, len(message_states)):
            if message_states[pos] != MessageState.CONFIRMED:
                return pos
        return len(message_states)
            
    def need_send(state : MessageState) -> bool:
        return True
    
class SelectiveRepeat:
    def name():
        return 'SelectiveRepeat'
    
    def move_window(prev_pos, message_states) -> int:
        for pos in range(prev_pos, len(message_states)):
            if message_states[pos] != MessageState.CONFIRMED:
                return pos
        return len(message_states)
            
    def need_send(state : MessageState) -> bool:
        return state != MessageState.CONFIRMED

class Sender:
    def __init__(self, timeouts, message_count) -> None:
        self.timeouts = timeouts
        self.message_count = message_count

    def run(self, data_size : int, window_size : int, timeout_ns : int, put, get, repeat_policy, senderStoped) -> None:
        message_states = [MessageState.PENDING for i in range(data_size)]
        timeouts = 0
        message_count = 0
        window_start = 0
        while True:
            window_start = repeat_policy.move_window(window_start, message_states)
            window_end = min(window_start + window_size, data_size)

            if window_start >= data_size:
                break

            window_states = [(MessageState.PENDING if repeat_policy.need_send(message_states[pos]) else MessageState.CONFIRMED) for pos in range(window_start, window_end)]

            current_send_count = 0

            for pos in range(window_start, window_end):
                if window_states[pos - window_start] == MessageState.PENDING:
                    put(Message(MessageType.DATA, pos))
                    window_states[pos - window_start] = message_states[pos] = MessageState.SENT
                    message_count += 1
                    current_send_count += 1
            
            last_sync_time_ns = time.time_ns()

            while time.time_ns() < last_sync_time_ns + timeout_ns and current_send_count > 0:
                try:
                    message = get(False)
                    if message.type == MessageType.CONFORMATION:
                        if message.index in range(window_start, window_end):
                            if window_states[message.index - window_start] == MessageState.SENT:
                                window_states[message.index - window_start] = message_states[message.index] = MessageState.CONFIRMED
                                current_send_count -= 1
                                last_sync_time_ns = time.time_ns()
                except Empty:
                    pass
            if current_send_count > 0:
                timeouts += 1
        senderStoped.set()
        with self.timeouts.get_lock():
            self.timeouts.value = timeouts
        with self.message_count.get_lock():
            self.message_count.value = message_count
        
class Receiver:
    def run(self, put, get, senderStoped) -> None:
        while not senderStoped.is_set():
            try:
                message = get(False)
                if message.type == MessageType.DATA:
                    put(Message(MessageType.CONFORMATION, message.index))
            except Empty:
                pass


def main():
    senderStoped = Event()

    timeouts = Value(ctypes.c_uint32)
    message_count = Value(ctypes.c_uint32)

    sender = Sender(timeouts, message_count)
    receiver = Receiver()

    data_size = 1000
    timeout_ns = 5000000

    window_sizes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    loss_probs = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    for policy in [SelectiveRepeat, GoBackN]:

        
        resultsK = []
        resultsTime = []

        for i, loss_prob in enumerate(loss_probs):
            resultsK.append([])
            resultsTime.append([])
            forwardChanel = OneWayChanel(0, loss_prob, np.random.rand)
            backwardChanel = OneWayChanel(0, 0.0, np.random.rand)

            for window in window_sizes:
                print(policy.name(), loss_prob, window)
                senderStoped.clear()
                timeouts.value = 0
                message_count.value = 0
                senderThread = Process(target=sender.run, args=(data_size, window, timeout_ns, forwardChanel.put, backwardChanel.get, policy, senderStoped))
                receiverThread = Process(target=receiver.run, args=(backwardChanel.put, forwardChanel.get, senderStoped))
                forwardChanelThread = Process(target=repeat_until, args=(forwardChanel.process, senderStoped))
                backwardChanelThread = Process(target=repeat_until, args=(backwardChanel.process, senderStoped))

                start_time = time.time()

                forwardChanelThread.start()
                backwardChanelThread.start()
                receiverThread.start()
                senderThread.start()

                senderThread.join()
                receiverThread.join()
                forwardChanelThread.join()
                backwardChanelThread.join()

                resultsK[i].append(data_size / message_count.value)
                resultsTime[i].append(time.time() - start_time)
            
        
        print(*([policy.name()] + window_sizes), sep = ';')
        for i, loss_prob in enumerate(loss_probs):
            print(*([loss_prob] + resultsK[i]), sep = ';')
            
        print(*([policy.name()] + window_sizes), sep = ';')
        for i, loss_prob in enumerate(loss_probs):
            print(*([loss_prob] + resultsTime[i]), sep = ';')


if __name__ == '__main__':
    main()