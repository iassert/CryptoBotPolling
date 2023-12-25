import asyncio
import logging

from aiogram            import Bot, types
from aiogram.types      import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils      import executor
from aiogram.bot.api    import TelegramAPIServer
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.contrib.middlewares.logging import LoggingMiddleware

from aiocryptopay import AioCryptoPay, Networks
from aiocryptopay.models.invoice import Invoice

from dill_storage import DillStorage

from asyncio import Event

logging.basicConfig(level = logging.INFO)


class Config:
    API_TOKEN: str
    CRYPTO_PAY_TOKEN: str
    CREATOR_ID: int

    LOCAL_SERVER: TelegramAPIServer = TelegramAPIServer.from_base('http://localhost:8081')


class cryptoExecutor(FSMContext):
    @staticmethod
    def start_polling() -> None:
        asyncio.create_task(cryptoExecutor.__polling())

    @staticmethod
    async def paid(invoice_id: int) -> bool:
        cryptoExecutor.__event.set()
        event = Event()

        cryptoExecutor.__invoices[invoice_id] = event

        return await event.wait()


    @staticmethod
    async def __polling() -> None:
        while True:
            if not cryptoExecutor.__invoices:
                await cryptoExecutor.__event.wait()
                cryptoExecutor.__event = Event()

            invoices = await Bot_.crypto.get_invoices(invoice_ids = [*cryptoExecutor.__invoices.keys()])
            for invoice in invoices:
                if invoice.status == "paid" and invoice.invoice_id in cryptoExecutor.__invoices:
                    cryptoExecutor.__invoices[invoice.invoice_id].set()
                    cryptoExecutor.__invoices.pop(invoice.invoice_id)

            await asyncio.sleep(cryptoExecutor.__DEFAULT_DALAY)


    __DEFAULT_DALAY: float = 0.300

    __event = Event()
    __invoices: dict[int, Event] = {}


class Markups:
    def invoice_inline(invoice: Invoice) -> InlineKeyboardMarkup:
        markup_ = InlineKeyboardMarkup()
        markup_.row(InlineKeyboardButton(f"{invoice.asset} {invoice.amount}", url = invoice.bot_invoice_url))

        return markup_


class Bot_:
    bot: Bot = Bot(token = Config.API_TOKEN, server = Config.LOCAL_SERVER)
    dp: Dispatcher = Dispatcher(bot, storage = DillStorage())
    dp.middleware.setup(LoggingMiddleware())

    timeout = 300

    crypto: AioCryptoPay = AioCryptoPay(token = Config.CRYPTO_PAY_TOKEN, network = Networks.MAIN_NET)


class Main:
    async def start(message: types.Message, state: FSMContext):
        #invoice = await Bot_.crypto.create_invoice(amount = 0.011, fiat = 'USD', currency_type = 'fiat')
        invoice = await Bot_.crypto.create_invoice(asset = 'USDT', amount = 0.01)

        await message.answer("Привет", reply_markup = Markups.invoice_inline(invoice))

        await cryptoExecutor.paid(invoice.invoice_id)

        await message.answer("✅ Есть оплата")


    async def on_startup(_):
        cryptoExecutor.start_polling()

        await Bot_.bot.send_message(Config.CREATOR_ID, "Бот запущен")

    async def on_shutdown(dp: Dispatcher):
        logging.warning('Shutting down..')

        await Bot_.bot.send_message(Config.CREATOR_ID, "Бот Выключен")

        logging.warning('Bye!')

    def main():
        try:
            executor.start_polling(
                dispatcher   = Bot_.dp,
                skip_updates = True,
                on_startup   = Main.on_startup,
                on_shutdown  = Main.on_shutdown,
                timeout      = Bot_.timeout,
            )
        except Exception as ex:
            logging.error(f"{ex.__class__.__name__}: {ex}")


Bot_.dp.register_message_handler(
    Main.start,
    commands = "start",
    state = "*"
)


if __name__ == "__main__":
    Main.main()
