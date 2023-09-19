from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, ReplyKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext, filters
from config import API_TOKEN, cursor, con
from datetime import datetime
import traceback


bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


inline_kb_full = InlineKeyboardMarkup()
status_kb = ReplyKeyboardMarkup()
instruction_btn = InlineKeyboardButton('▶️ Инструкция по PinDuoDuo', callback_data='instruction')
inline_kb_full.row(instruction_btn)
status_kb.add(InlineKeyboardButton('Новый', callback_data='btn_new'), InlineKeyboardButton('Отправлена', callback_data='btn_sent'), InlineKeyboardButton('На складе', callback_data='btn_arrived'))

# классы машины состояний
class UserState(StatesGroup):
    name = State()
    package_id = State()

class userInfo(StatesGroup):
    city = State()
    phone_num = State()

class userStatus(StatesGroup):
    packages = State()

class packageStatusArrived(StatesGroup):
    packages = State()

class Broadcast(StatesGroup):
    text = State()

class delPackages(StatesGroup):
    packages_id = State()

# кнопка с инструкцией
@dp.callback_query_handler(text='instruction')
async def instruction_button(callback_query: types.CallbackQuery): 
    # нужно вставить ссылку на gif
    await bot.send_animation(callback_query.from_user.id, 
                             animation='https://techcrunch.com/wp-content/uploads/2014/02/telegram-rise2-2.gif?w=1390&crop=1',
                             caption='☝️ ☝️ ☝️\nВот инструкция как добавлять свой адрес в PinDuoDuo.')

# добавить посылку
@dp.message_handler(commands='add_package')
async def add_package(message: types.Message):
    await message.reply(
"""
✍️ Напишите НАЗВАНИЕ для своей посылки, чтобы потом легко её найти среди других своих посылок.\n
ℹ️ Например: Куртка Gucci или Диван для зала
"""
    )
    await UserState.name.set()

@dp.message_handler(state=UserState.name)
async def get_package_id(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    data = await state.get_data()
    if data['name'] == 'отменить':
        await state.finish()
        await bot.send_message(message.from_user.id, text='Добавление посылки отменено')
    else:
        await message.answer(
f"""🆗 Отлично!
Добавляем посылку с названием "{data['name']}"\n
#️⃣ Теперь нужно указать трек-код своей посылки полученный с сайта PinDuoDuo, 1688 или Taobao.\n
ℹ️ Пример: CN9320827864СТ
"""
        )
        await UserState.package_id.set() 


@dp.message_handler(state=UserState.package_id)
async def finish_creating(message: types.Message, state: FSMContext):
    await state.update_data(package_id=message.text)
    data = await state.get_data()
    await message.reply(
f"""🥳 Класс! Ну вот и всё!\n\n
✅ Посылка "{data['name']}" с трек-кодом {data['package_id']} успешно добавлена!\n
-----------------------------------\n
🔔 Как только ваша посылка придёт к нам в офис мы отправим вам здесь сообщение об этом.\n
🚚 И потом вы сможете отслеживать свою посылку до получения её на руки.
"""
    )

    now = datetime.now()
    dt_string = (now.strftime("%d/%m/%Y")).replace('/', '.')
    cursor.execute(f'INSERT INTO users (tg_id, package_id, package_name, time, status) VALUES ({message.from_user.id}, "{data["package_id"]}", "{data["name"]}", "{dt_string}", "Новый")')
    con.commit()

    await state.finish()
    
    if len((cursor.execute(f'SELECT * FROM users_info WHERE tg_id = {message.from_user.id}')).fetchall()) == 0:
        await bot.send_message(message.from_user.id, text=
"""Сейчас мы один раз укажем ваш город.\n
🏙️ КАКОЙ У ВАС ГОРОД?
(пример: Алматы или Алматинская обл, г.Талдыкорган)
"""
                         )
        await userInfo.city.set()

@dp.message_handler(state=userInfo.city)
async def get_user_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.reply(
"""☎️ И ваш НОМЕР ТЕЛЕФОНА для связи по WhatsApp:
(пример: 8 777 123 45 67)
"""
    )
    await userInfo.phone_num.set()

@dp.message_handler(state=userInfo.phone_num)
async def get_user_city(message: types.Message, state: FSMContext):
    await state.update_data(phone_num=message.text)
    data = await state.get_data()
    await message.reply(
f"""📮 ВЫ УКАЗАЛИ:\n
🏙️ город: {data["city"]}
☎️ телефон: {data["phone_num"]}
"""
    )
    cursor.execute(f'INSERT INTO users_info (tg_id, city, phone_number) VALUES ({message.from_user.id}, "{data["city"]}", "{data["phone_num"]}")')
    con.commit()
    await state.finish()


# просмотр посылок
@dp.message_handler(commands='check_packages')
async def check_packages(message: types.Message):
    await message.reply('📋 ВСЕ ВАШИ ПОСЫЛКИ:')
    packages = cursor.execute(f'SELECT package_id, package_name, status, time, sent_time, arrived_time, weight, price FROM users WHERE tg_id = {message.from_user.id}')
    fet = packages.fetchall()
    if len(fet) == 0:
        await message.reply(
"""😱 Ой, а у Вас пока нет посылок...\n\n
Вы уверены, что уже добавляли посылку?\n\n
Мы не смогли ничего найти. Возможно посылка уже была доставлена вам на руки.""")
    else:
        for i in fet:
            sent = f"\n📅 Отправлен: {i[4]}" if i[4] != None else ""
            arrived = f"\n📅 Доставлено: {i[5]}" if i[5] != None else ""
            weight = f"\n⚖️ Вес: {i[6]}" if i[6] != None else ""
            price = f"\n💵 Цена: {i[7]}" if i[7] != None else ""
            text = f"🆔 Ваш заказ: {i[1]}\n#️⃣ Трек-код: {i[0]}\n📦 Статус: {i[2]}\n📅 Создан: {i[3]}" + sent + arrived + weight + price
            await bot.send_message(message.from_user.id, text=text)
    await bot.send_message(message.from_user.id, text='Пока это всё 👍🏻')

# добавление иформации о товаре
@dp.message_handler(commands='add_pack_info', commands_prefix='/')
async def add_pack_info(message: types.Message):
    if len(message.text.split()) != 4:
        await message.reply('Не верное кол-во аргументов! Требуется указать id посылки, вес и цену.\nПример:\n/add_pack_info CT9320827864СТ 2 2000')
    else:
        comment = message.text.split()[1:]
    try:
        cursor.execute(f'UPDATE users SET weight = "{comment[1]}", price = "{comment[2]}" WHERE package_id = "{comment[0]}"')
        con.commit()
        await bot.send_message(message.from_user.id, text='Информация добавлена')
    except Exception as error:
        await bot.send_message(message.from_user.id, text='Возникла ошибка при добавлении информации к посылке')
        print(error)


# присвоить статус "в пути"
@dp.message_handler(commands='set_status_sent')
async def set_status_sent(message: types.Message):
    await message.reply('Каким посылкам вы бы хотели присвоить статус "В пути"?')
    await userStatus.packages.set()

@dp.message_handler(state=userStatus.packages)
async def set_status_sent2(message: types.Message, state: FSMContext):
    await state.update_data(packages=message.text)
    data = await state.get_data()
    for i in (data['packages']).split():
        try:
            now = datetime.now()
            dt_string = (now.strftime("%d/%m/%Y")).replace('/', '.')
            cursor.execute(f'UPDATE users SET status = "В пути", sent_time = "{dt_string}" WHERE package_id = "{i}"')
            con.commit()
            users = (cursor.execute(f'SELECT tg_id, package_name FROM users WHERE package_id = "{i}"')).fetchall()
            await bot.send_message(users[0][0], text=f'Изменен статус вашей посылки {users[0][1]}! Товар отправился в Алматы.')
        except Exception:
            await bot.send_message(message.from_user.id, text=f'Не удалось обновить статус у посылки {i}, проверте правильность трек номера.')
            traceback.print_exc()
    await state.finish()

# присвоить статус "Прибыл"
@dp.message_handler(commands='set_status_arrived')
async def set_status_arrived(message: types.Message):
    await message.reply('Каким посылкам вы бы хотели присвоить статус "Прибыл"?')
    await packageStatusArrived.packages.set()

@dp.message_handler(state=packageStatusArrived.packages)
async def set_status_arrived2(message: types.Message, state: FSMContext):
    await state.update_data(packages=message.text)
    data = await state.get_data()
    data = (data['packages']).split('\n')
    for i in data:
        i = i.split()
        package_id = i[0]
        weight = " ".join(i[1:3])
        price = " ".join(i[3:])
        try:
            now = datetime.now()
            dt_string = (now.strftime("%d/%m/%Y")).replace('/', '.')
            cursor.execute(f'UPDATE users SET status = "Прибыл", weight = "{weight}", price = "{price}", arrived_time = "{dt_string}" WHERE package_id = "{package_id}"')
            con.commit()
            users = (cursor.execute(f'SELECT tg_id, package_name FROM users WHERE package_id = "{package_id}"')).fetchall()
            await bot.send_message(users[0][0], text=f'Изменен статус вашей посылки "{users[0][1]}"! Товар прибыл на склад. Вес: {weight}, Цена: {price}')
        except Exception:
            await bot.send_message(message.from_user.id, text=f'Не удалось обновить статус у посылки {package_id}, проверте правильность трек номера.')
            traceback.print_exc()
    await state.finish()


# Удалить посылки из бд
@dp.message_handler(commands='del_packs')
async def delete_packages_from_db(message: types.Message):
    await message.reply('Какие посылки вы бы хотели удалить?')
    await delPackages.packages_id.set()

@dp.message_handler(state=delPackages.packages_id)
async def delete_packages_from_db2(message: types.Message, state: FSMContext):
    await state.update_data(packages=message.text)
    data = await state.get_data()
    data = (data['packages']).split('\n')
    for i in data:
        try:
            cursor.execute(f'DELETE FROM users WHERE package_id = "{i}"')
            con.commit()
        except Exception:
            await bot.send_message(message.from_user.id, text=f'Не удалось удалить посылку {i}, проверте правильность трек номера.')
            traceback.print_exc()
    await bot.send_message(message.from_user.id, text='Посылки успешно удалены')
    await state.finish()



# рассылка сообщений
@dp.message_handler(commands='broadcast', commands_prefix='/')
async def broadcast(message: types.Message):
    await message.reply('Введите текст рассылки')
    await Broadcast.text.set()

@dp.message_handler(state=Broadcast.text)
async def broadcast_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    data = await state.get_data()
    await message.reply('Рассылка отправляется...')
    users = (cursor.execute(f'SELECT tg_id FROM users_info')).fetchall()
    for i in users:
        await bot.send_message(i[0], text=data["text"])
    await state.finish()



@dp.message_handler(commands='start', commands_prefix='/')
async def start(message: types.Message):
    try:
        cursor.execute(f'INSERT INTO users_id (tg_id) VALUES ({message.from_user.id})')
        con.commit()
    except:
        pass
    id = ((cursor.execute(f'SELECT id FROM users_id WHERE tg_id = {message.from_user.id}')).fetchall())[0][0]
    num = [4 - len(str(id)) if len(str(id)) < 5 else 0]
    id = '0'*num[0] + str(id)

    await message.reply(
f"""
👋 Здравствуйте, {message.from_user.full_name}!

ДОБРО ПОЖАЛОВАТЬ в сервис доставки посылок из Китая - AliPapa

Теперь вы можете получать все свои заказы из 🇨🇳 Китая быстро и недорого!

🪙 Стоимость доставки за 1 кг 2100 тг.
Мы даем такие цены только для мелких заказов из PinDuoDuo, 1688 и Taobao.


⏳ Сроки доставки до Алматы: 15-18 дней.""")
    await bot.send_message(
text=f"""
🪪 ВАШ АККАУНТ в AliPapa:

🆔 👉```Ais-{id}```👈
(☝️нажмите и скопируйте)


🇨🇳 Для отправки товаров на наш склад в Китае, пожалуйста, используйте следующий адрес:

⏺️ ТЕЛЕФОН КАРГО
👉```15910292807```👈
(☝️нажмите и скопируйте)


🏪 АДРЕС В КИТАЕ
👉```广州市白云区同德街道西槎路603-613号溪雨国际广场D103号866库房```👈
(☝️нажмите и скопируйте)

и добавьте в конце - ```87771234567``` (Казахстанский номер) - Aidana (Ваше имя)
""", chat_id=message.from_user.id, parse_mode=ParseMode.MARKDOWN, reply_markup=inline_kb_full
    )
        

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
