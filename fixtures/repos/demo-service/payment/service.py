# Payment Service

class Gateway:
    def charge(self, amount, card):
        pass

gateway = Gateway()

def validate_amount(amount):
    if amount <= 0:
        raise ValueError('Amount must be positive')
    if amount > 10000:
        raise ValueError('Amount exceeds maximum')
    return True

def process_payment(amount, card):
    validate_amount(amount)
    return gateway.charge(amount, card)
