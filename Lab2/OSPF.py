import numpy as np
import enum
import time
from multiprocessing import Process, Event, Queue, Value
from queue import Empty
from queue import Queue as SimpleQueue
import ctypes
import copy

class ChanelMessage:
    def __init__(self, adress_id : int, payload = None) -> None:
        self.adress_id = adress_id
        self.payload = payload

class FlyingMessage:
    def __init__(self, message : ChanelMessage, start_time_ns : int) -> None:
        self.message = message
        self.start_time_ns = start_time_ns

class ManyWayChanel:
    def __init__(self, adress_count, time_to_pass_ns : int, loss_probability, rand) -> None:
        self.adress_count = adress_count
        self.input_queue = Queue()
        self.flying_queue = Queue()
        self.output_queues = [Queue() for i in range(adress_count)]
        self.rand = rand
        self.time_to_pass_ns = time_to_pass_ns
        self.loss_probability = loss_probability
        self.flying_message = None

    def put(self, msg : ChanelMessage, block=True):
        if msg.adress_id >= self.adress_count:
            raise ValueError(f"Invalid adress id")
        self.input_queue.put(msg, block)

    def get(self, adress_id, block=True) -> ChanelMessage:
        if adress_id >= self.adress_count:
            raise ValueError(f"Invalid adress id")
        return self.output_queues[adress_id].get(block)

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
                self.output_queues[self.flying_message.message.adress_id].put(self.flying_message.message)
            self.flying_message = None
    
    def process(self) -> None:
        time.sleep(0.0001)
        self.process_input()
        self.process_output()

class OSPFMessageType(enum.Enum):
    DATA = enum.auto()
    HELLOW = enum.auto()
    LSA = enum.auto()
    DB = enum.auto()
    DB_REQUEST = enum.auto()
    
class OSPFMessage:
    def __init__(self, type : OSPFMessageType, router_id : int, payload = None) -> None:
        self.type = type
        self.router_id = router_id
        self.payload = payload

class LSAData:
    def __init__(self, neighbor_ids : list[int]) -> None:
        self.neighbor_ids = neighbor_ids

class DBData:
    def __init__(self, topology) -> None:
        self.topology = topology


HELLOW_INTERVAL = 0.5 * 1000000000
DEAD_INTERVAL = 1.0 * 1000000000
RESEND_INTERVAL = 0.2 * 1000000000


class OSPFDesignatedRouter:
    def __init__(self, chanel : ManyWayChanel, router_id : int) -> None:
        self.chanel = chanel
        self.router_id = router_id
        self.adress_count = self.chanel.adress_count - 1
        self.last_hellow_sent = [None for i in range(self.adress_count)]
        self.topology = [set() for i in range(self.adress_count)]
        self.needSend = None
        self.last_send_time = None
    
    def process(self):
        time.sleep(0.0001)
        self.send_hellow()
        self.process_messages()
        self.send_messages()
    
    def send_hellow(self):
        for router_id, hellow_sent in enumerate(self.last_hellow_sent):
            if (hellow_sent is None) or (time.time_ns() >= hellow_sent + HELLOW_INTERVAL):
                self.last_hellow_sent[router_id] = time.time_ns()
                self.chanel.put(ChanelMessage(router_id, OSPFMessage(OSPFMessageType.HELLOW, self.router_id)))

    def process_messages(self):
        try:
            while True:
                message : OSPFMessage = self.chanel.get(self.router_id, False).payload
                if message.type == OSPFMessageType.DATA:
                    pass
                elif message.type == OSPFMessageType.HELLOW:
                    pass
                elif message.type == OSPFMessageType.LSA:
                    data : LSAData = message.payload
                    if len(self.topology[message.router_id].symmetric_difference(data.neighbor_ids)) > 0:
                        self.needSend = True
                        self.topology[message.router_id] = set(data.neighbor_ids)
                elif message.type == OSPFMessageType.DB:
                    pass
                elif message.type == OSPFMessageType.DB_REQUEST:
                    self.needSend = True
        except Empty:
            pass

    def send_messages(self):
        if (not self.needSend):
            return
        if (self.last_send_time is None) or (time.time_ns() >= self.last_send_time + RESEND_INTERVAL):
            for router_id in range(self.adress_count):
                self.chanel.put(ChanelMessage(router_id, OSPFMessage(OSPFMessageType.DB, self.router_id, DBData(copy.deepcopy(self.topology)))))
            self.last_send_time = time.time_ns()
            self.needSend = False
        

class OSPFRouter:
    def __init__(self, chanel : ManyWayChanel, router_id : int, dr_id : int, neighbor_ids : list[int]) -> None:
        self.chanel = chanel
        self.router_id = router_id
        self.adress_count = self.chanel.adress_count - 1
        self.dr_id = dr_id
        self.dr_dead = True
        self.dr_last_hellow_sent = None
        self.dr_last_hellow_got = None
        self.neighbor_ids = neighbor_ids
        self.dead = [True for i in range(len(neighbor_ids))]
        self.last_hellow_sent = [None for i in range(len(neighbor_ids))]
        self.last_hellow_got = [None for i in range(len(neighbor_ids))]
        self.topology = None
        self.shortest_paths = None
        self.shortest_paths_first = None
        self.last_send_time = None
        self.pending_DB_request : OSPFMessage = OSPFMessage(OSPFMessageType.DB_REQUEST, self.router_id)
        self.data_queue = Queue()
    
    def process(self):
        time.sleep(0.0001)
        self.send_hellow()
        self.process_messages()
        if (not self.topology is None) and (self.shortest_paths is None):
            self.update_shortest_paths()
        self.update_dead()
        self.send_messages()
    
    def send_hellow(self):
        if (self.dr_last_hellow_sent is None) or (time.time_ns() >= self.dr_last_hellow_sent + HELLOW_INTERVAL):
            self.dr_last_hellow_sent = time.time_ns()
            self.chanel.put(ChanelMessage(self.dr_id, OSPFMessage(OSPFMessageType.HELLOW, self.router_id)))
        for id, neighbor_id in enumerate(self.neighbor_ids):
            if (self.last_hellow_sent[id] is None) or (time.time_ns() >= self.last_hellow_sent[id] + HELLOW_INTERVAL):
                self.last_hellow_sent[id] = time.time_ns()
                self.chanel.put(ChanelMessage(neighbor_id, OSPFMessage(OSPFMessageType.HELLOW, self.router_id)))

    def skip_messages(self):
        try:
            while True:
                message : OSPFMessage = self.chanel.get(self.router_id, False).payload
        except Empty:
            pass

    def process_messages(self):
        try:
            while True:
                message : OSPFMessage = self.chanel.get(self.router_id, False).payload
                if message.type == OSPFMessageType.DATA:
                    self.send_data(message)

                elif message.type == OSPFMessageType.HELLOW:
                    if message.router_id == self.dr_id:
                        self.dr_last_hellow_got = time.time_ns()
                    else:
                        try:
                            id = self.neighbor_ids.index(message.router_id)
                            self.last_hellow_got[id] = time.time_ns()
                        except:
                            pass
                elif message.type == OSPFMessageType.LSA:
                    pass
                elif message.type == OSPFMessageType.DB:
                    self.pending_DB_request = None
                    self.topology = message.payload.topology
                    self.shortest_paths = None
                elif message.type == OSPFMessageType.DB_REQUEST:
                    pass
        except Empty:
            pass
        
    def update_shortest_paths(self):
        self.shortest_paths = [None for i in range(self.adress_count)]

        visited = set()
        pending = SimpleQueue()
        pending.put(self.router_id)
        visited.add(self.router_id)
        self.shortest_paths[self.router_id] = self.router_id

        while not pending.empty():
            cur_id = pending.get()
            for node_id in self.topology[cur_id]:
                if (node_id in visited):
                    continue
                visited.add(node_id)
                pending.put(node_id)
                self.shortest_paths[node_id] = cur_id
        
        self.shortest_paths_first = [None for i in range(self.adress_count)]
        for node_id in range(self.adress_count):
            prev = self.shortest_paths[node_id]
            if prev is None:
                continue
            self.shortest_paths_first[node_id] = node_id
            while prev != self.router_id:
                self.shortest_paths_first[node_id] = prev
                prev = self.shortest_paths[prev]

    def update_dead(self):
        if (self.dr_last_hellow_got is None) or (time.time_ns() >= self.dr_last_hellow_got + DEAD_INTERVAL):
            self.dr_dead = True
        else:
            self.dr_dead = False
        for id, hellow_got in enumerate(self.last_hellow_got):
            if (hellow_got is None) or (time.time_ns() >= hellow_got + DEAD_INTERVAL):
                self.dead[id] = True
            else:
                self.dead[id] = False

    def send_messages(self):
        if self.dr_dead:
            return
        if not self.pending_DB_request is None:
            if (self.last_send_time is None) or (time.time_ns() >= self.last_send_time + RESEND_INTERVAL):
                self.chanel.put(ChanelMessage(self.dr_id, self.pending_DB_request))
                self.last_send_time = time.time_ns()
        elif (not self.topology is None) and ((self.last_send_time is None) or (time.time_ns() >= self.last_send_time + RESEND_INTERVAL)):
            for neighbor_id, dead in zip(self.neighbor_ids, self.dead):
                if dead == (neighbor_id in self.topology[self.router_id]):
                    live = []
                    for neighbor_id, dead in zip(self.neighbor_ids, self.dead):
                        if not dead:
                            live.append(neighbor_id)
                    self.chanel.put(ChanelMessage(self.dr_id, OSPFMessage(OSPFMessageType.LSA, self.router_id, LSAData(live))))
                    self.last_send_time = time.time_ns()
                    break

    def send_data(self, message):
        if message.router_id == self.router_id:
            self.data_queue.put(message.payload)
            return
        if (self.shortest_paths is None) or (self.shortest_paths[message.router_id] is None):
            return

        neighbor_id = self.shortest_paths_first[message.router_id]
        id = self.neighbor_ids.index(neighbor_id)
        if self.dead[id]:
            return

        self.chanel.put(ChanelMessage(neighbor_id, message))
    
    def put(self, router_id, data):
        self.chanel.put(ChanelMessage(self.router_id, OSPFMessage(OSPFMessageType.DATA, router_id, data)))
    
    def get(self):
        return self.data_queue.get(False)




    




class SelectiveRepeatMessageState(enum.Enum):
    PENDING = enum.auto()
    SENT = enum.auto()
    RECEIVED = enum.auto()
    CONFIRMED = enum.auto()

class SelectiveRepeatMessageType(enum.Enum):
    DATA = enum.auto()
    CONFORMATION = enum.auto()

class SelectiveRepeatMessage:
    def __init__(self, type : SelectiveRepeatMessageType, index : int, payload = None) -> None:
        self.type = type
        self.index = index
        self.payload = payload

def repeat_until(work, stop) -> None:
    while(not stop.is_set()):
        work()
    return
    
class SelectiveRepeat:
    def name():
        return 'SelectiveRepeat'
    
    def move_window(prev_pos, message_states) -> int:
        for pos in range(prev_pos, len(message_states)):
            if message_states[pos] != SelectiveRepeatMessageState.CONFIRMED:
                return pos
        return len(message_states)
            
    def need_send(state : SelectiveRepeatMessageState) -> bool:
        return state != SelectiveRepeatMessageState.CONFIRMED

class Sender:
    def __init__(self, timeouts, message_count) -> None:
        self.timeouts = timeouts
        self.message_count = message_count

    def run(self, data_size : int, window_size : int, timeout_ns : int, put, get, repeat_policy, senderStoped) -> None:
        message_states = [SelectiveRepeatMessageState.PENDING for i in range(data_size)]
        timeouts = 0
        message_count = 0
        window_start = 0
        while True:
            window_start = repeat_policy.move_window(window_start, message_states)
            window_end = min(window_start + window_size, data_size)

            if window_start >= data_size:
                break

            window_states = [(SelectiveRepeatMessageState.PENDING if repeat_policy.need_send(message_states[pos]) else SelectiveRepeatMessageState.CONFIRMED) for pos in range(window_start, window_end)]

            current_send_count = 0

            for pos in range(window_start, window_end):
                if window_states[pos - window_start] == SelectiveRepeatMessageState.PENDING:
                    put(1, SelectiveRepeatMessage(SelectiveRepeatMessageType.DATA, pos))
                    window_states[pos - window_start] = message_states[pos] = SelectiveRepeatMessageState.SENT
                    message_count += 1
                    current_send_count += 1
            
            last_sync_time_ns = time.time_ns()

            while time.time_ns() < last_sync_time_ns + timeout_ns and current_send_count > 0:
                try:
                    message : SelectiveRepeatMessage = get()
                    if message.type == SelectiveRepeatMessageType.CONFORMATION:
                        if message.index in range(window_start, window_end):
                            if window_states[message.index - window_start] == SelectiveRepeatMessageState.SENT:
                                window_states[message.index - window_start] = message_states[message.index] = SelectiveRepeatMessageState.CONFIRMED
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
                message : SelectiveRepeatMessage = get()
                if message.type == SelectiveRepeatMessageType.DATA:
                    put(0, SelectiveRepeatMessage(SelectiveRepeatMessageType.CONFORMATION, message.index))
            except Empty:
                pass


def main():
    senderStoped = Event()
    chanelStoped = Event()

    timeouts = Value(ctypes.c_uint32)
    message_count = Value(ctypes.c_uint32)

    sender = Sender(timeouts, message_count)
    receiver = Receiver()

    data_size = 1000
    timeout_ns = 0.01 * 1000000000

    window_sizes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    loss_probs = [0.00, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64]
    for policy in [SelectiveRepeat]:

        
        resultsK = []
        resultsTime = []

        for i, loss_prob in enumerate(loss_probs):
            resultsK.append([])
            resultsTime.append([])

            chanelStoped.clear()
            forwardChanel = ManyWayChanel(8, 0, loss_prob, np.random.rand)
            forwardChanelThread = Process(target=repeat_until, args=(forwardChanel.process, chanelStoped))
            forwardChanelThread.start()

            for window in window_sizes:
                print(policy.name(), loss_prob, window)
                senderStoped.clear()
                timeouts.value = 0
                message_count.value = 0
                dr = OSPFDesignatedRouter(forwardChanel, 7)
                sender_router = OSPFRouter(forwardChanel, 0, 7, [2,3,4,5,6])
                receiver_router = OSPFRouter(forwardChanel, 1, 7, [2,3,4,5,6])
                other_router2 = OSPFRouter(forwardChanel, 2, 7, [0,1])
                other_router3 = OSPFRouter(forwardChanel, 3, 7, [0,1])
                other_router4 = OSPFRouter(forwardChanel, 4, 7, [0,1])
                other_router5 = OSPFRouter(forwardChanel, 5, 7, [0,1])
                other_router6 = OSPFRouter(forwardChanel, 6, 7, [0,1])
                senderThread = Process(target=sender.run, args=(data_size, window, timeout_ns, sender_router.put, sender_router.get, policy, senderStoped))
                receiverThread = Process(target=receiver.run, args=(receiver_router.put, receiver_router.get, senderStoped))
                drThread = Process(target=repeat_until, args=(dr.process, senderStoped))
                sender_routerThread = Process(target=repeat_until, args=(sender_router.process, senderStoped))
                receiver_routerThread = Process(target=repeat_until, args=(receiver_router.process, senderStoped))
                other_router2Thread = Process(target=repeat_until, args=(other_router2.process, senderStoped))
                other_router3Thread = Process(target=repeat_until, args=(other_router3.process, senderStoped))
                other_router4Thread = Process(target=repeat_until, args=(other_router4.process, senderStoped))
                other_router5Thread = Process(target=repeat_until, args=(other_router5.process, senderStoped))
                other_router6Thread = Process(target=repeat_until, args=(other_router6.process, senderStoped))

                start_time = time.time()

                receiverThread.start()
                senderThread.start()
                drThread.start()
                sender_routerThread.start()
                receiver_routerThread.start()
                other_router2Thread.start()
                other_router3Thread.start()
                other_router4Thread.start()
                other_router5Thread.start()
                other_router6Thread.start()

                senderThread.join()
                print("join senderThread")
                receiverThread.join()
                print("join receiverThread")
                drThread.join()
                print("join drThread")
                sender_routerThread.join()
                print("join sender_routerThread")
                receiver_routerThread.join()
                print("join receiver_routerThread")
                other_router2Thread.join()
                other_router3Thread.join()
                other_router4Thread.join()
                other_router5Thread.join()
                other_router6Thread.join()
                print("join other_routerThread")

                resultsK[i].append(data_size / message_count.value)
                resultsTime[i].append(time.time() - start_time)
            
            chanelStoped.set()

            forwardChanelThread.join()
            print("join forwardChanelThread")
            
        
        print(*([policy.name()] + window_sizes), sep = ';')
        for i, loss_prob in enumerate(loss_probs):
            print(*([loss_prob] + resultsK[i]), sep = ';')
            
        print(*([policy.name()] + window_sizes), sep = ';')
        for i, loss_prob in enumerate(loss_probs):
            print(*([loss_prob] + resultsTime[i]), sep = ';')


if __name__ == '__main__':
    main()