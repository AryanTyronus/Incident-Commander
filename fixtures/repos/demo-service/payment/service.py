# Payment Service

class Gateway:
    def charge(self, amount, card):
        pass

gateway = Gateway()

def process_payment(amount, card):
    if amount > 1000:
        raise ValueError('Amount too high')
    return gateway.charge(amount, card)
