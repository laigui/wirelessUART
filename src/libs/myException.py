class RxTimeOutError(Exception):
    def __init__(self, rx_cnt, expected, seconds):
        self.rx_cnt = rx_cnt
        self.expected = expected
        self.seconds = seconds

    def __str__(self):
        message = 'not receive {0} bytes within {1} seconds, only got {2} bytes'.format(self.expected,self.seconds, self.rx_cnt)
        return message


if __name__ == "__main__":
    raise RxTimeOutError(4,10,5)
