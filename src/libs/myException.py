class RxTimeOutError(Exception):
    def __init__(self, rx_str, n, seconds):
        self.rx_str = rx_str
        self.n = n
        self.seconds = seconds

    def __str__(self):
        message = 'RX: {0}\nexpect {1} bytes within {2} seconds'.format(self.rx_str, self.n, self.seconds)
        return message

class RxNack(Exception):
    pass

class RxTimeOut(Exception):
    pass

if __name__ == "__main__":
    print RxTimeOutError('abcd',10,5)
