import random
import SRP


class Player:
    def __init__(self):
        self.SRP_reciever = SRP.SRPReceiver()
        self.SRP_sender = SRP.SRPSender()
        self.fast = False
        self.path = None

    def isWon(self):
        return self.SRP_sender.isDone()

    def progress(self):
        if self.isWon():
            return 100
        else:
            return int(100 * self.SRP_sender.ans_count / (self.SRP_sender.max_number + 1))

    def sendAndReceiveMsg(self, intermediate_points, source_point):
        if self.path is None or len(self.path) == 0:
            return
        for j in range(len(self.path) - 1):
            intermediate_points[self.path[j]].connect(intermediate_points[self.path[j + 1]].pos)
            
        intermediate_points[self.path[-1]].connect(source_point.pos)
        # send one message to each other
        if self.SRP_sender.send_msg_queue.has_msg():
            for j in range(len(self.path)):
                if not intermediate_points[self.path[j]].active:
                    break
                intermediate_points[self.path[j]].health -= intermediate_points[self.path[j]].heat_mult
            self.SRP_reciever.recieve_msg_queue.send_message(self.SRP_sender.send_msg_queue.get_message())
        if self.SRP_reciever.send_msg_queue.has_msg():
            for i in range(len(self.path)):
                j = len(self.path) - i - 1
                if not intermediate_points[self.path[j]].active:
                    break
                intermediate_points[self.path[j]].health -= intermediate_points[self.path[j]].heat_mult
            self.SRP_sender.recieve_msg_queue.send_message(self.SRP_reciever.send_msg_queue.get_message())
    
    def setPath(self, path):
        self.path = path

    def update(self):
        # update receiver
        self.SRP_sender.update()
        self.SRP_reciever.update()
        return False