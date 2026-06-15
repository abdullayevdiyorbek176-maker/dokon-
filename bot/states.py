from aiogram.fsm.state import State, StatesGroup


class AuthSt(StatesGroup):
    choosing_action = State()
    entering_shop_name = State()   # yangi dokon: nomi
    setting_login = State()        # yangi dokon: login o'rnatish
    setting_password = State()     # yangi dokon: parol o'rnatish
    entering_login = State()       # mavjud dokon: login kirish
    entering_password = State()    # mavjud dokon: parol kirish


class ProductSt(StatesGroup):
    menu = State()
    entering_name = State()
    entering_category = State()
    entering_buy_price_som = State()
    entering_buy_price_usd = State()
    entering_sell_price_som = State()
    entering_sell_price_usd = State()
    entering_stock = State()
    entering_min_stock = State()
    entering_unit = State()
    selecting = State()
    editing_field = State()
    editing_value = State()


class CategorySt(StatesGroup):
    entering_name = State()


class PurchaseSt(StatesGroup):
    selecting_supplier = State()
    adding_item_product = State()
    adding_item_qty = State()
    adding_item_price_som = State()
    adding_item_price_usd = State()
    entering_paid_som = State()
    confirming = State()


class SaleSt(StatesGroup):
    selecting_customer = State()
    adding_item_product = State()
    adding_item_qty = State()
    entering_discount = State()
    selecting_payment_method = State()
    entering_paid_som = State()
    entering_paid_usd = State()
    confirming = State()


class CustomerSt(StatesGroup):
    entering_name = State()
    entering_phone = State()
    selected = State()
    paying_debt_som = State()
    paying_debt_usd = State()
    editing_name = State()
    editing_phone = State()


class SupplierSt(StatesGroup):
    entering_name = State()
    entering_phone = State()
    selected = State()
    paying_debt_som = State()
    paying_debt_usd = State()


class ExpenseSt(StatesGroup):
    selecting_category = State()
    entering_amount_som = State()
    entering_amount_usd = State()
    entering_description = State()


class StaffSt(StatesGroup):
    entering_telegram_id = State()
    confirming_delete = State()


class ReportSt(StatesGroup):
    selecting_period = State()
    selecting_export = State()


class SettingsSt(StatesGroup):
    main = State()
    entering_usd_rate = State()
    entering_min_stock = State()


class KassaSt(StatesGroup):
    entering_handover_amount = State()
    entering_handover_recipient = State()
    entering_manual_amount = State()
    entering_manual_note = State()
