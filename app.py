import logging, os, secrets, sqlite3
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

TOKEN=os.getenv('BOT_TOKEN','').strip(); PORT=int(os.getenv('PORT','10000')); URL=os.getenv('RENDER_EXTERNAL_URL','').rstrip('/'); SECRET=os.getenv('WEBHOOK_SECRET') or secrets.token_urlsafe(24); ADMIN=os.getenv('ADMIN_USERNAME','Mikhail7890').lstrip('@').lower(); DB=os.getenv('DB_PATH','coolclass.db')
if not TOKEN: raise RuntimeError('BOT_TOKEN is not set')
if not URL: raise RuntimeError('RENDER_EXTERNAL_URL is not available')
logging.basicConfig(level=logging.INFO); log=logging.getLogger('coolclass')
bot=Bot(TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); dp=Dispatcher(storage=MemoryStorage())

class Lead(StatesGroup): parent=State(); child=State(); phone=State(); interest=State(); question=State()

def conn():
 c=sqlite3.connect(DB); c.execute('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)'); c.commit(); return c

def get(k):
 c=conn(); r=c.execute('SELECT v FROM settings WHERE k=?',(k,)).fetchone(); c.close(); return r[0] if r else None

def put(k,v):
 c=conn(); c.execute('INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',(k,v)); c.commit(); c.close()

def menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🏫 О школе'),KeyboardButton(text='📚 Программа')],[KeyboardButton(text='🕘 Расписание'),KeyboardButton(text='💰 Стоимость')],[KeyboardButton(text='📍 Как нас найти'),KeyboardButton(text='🎓 Записаться')],[KeyboardButton(text='❓ Задать вопрос')]],resize_keyboard=True)
def phone_menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='📱 Отправить номер телефона',request_contact=True)],[KeyboardButton(text='↩️ Отмена')]],resize_keyboard=True,one_time_keyboard=True)
def interest_menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🎓 Поступление'),KeyboardButton(text='🏫 Перевод в школу')],[KeyboardButton(text='👀 Экскурсия'),KeyboardButton(text='❓ Пока просто узнаю')]],resize_keyboard=True)
async def admin(text):
 cid=get('admin_chat_id')
 if cid:
  try: await bot.send_message(cid,text)
  except Exception: log.exception('admin notification failed')
 else: log.warning('admin_chat_id is empty; owner must press /start')

def group(m): return m.chat.type in ('group','supergroup')
def cmd(text):
 s=(text or '').strip().lower(); return (s.split()[0].split('@')[0] if s else '')

@dp.message(CommandStart())
async def start(m:Message,state:FSMContext):
 await state.clear()
 if group(m): return await m.answer('👋 <b>Добро пожаловать в группу CoolClass!</b>\n\n/расписание — расписание\n/стоимость — стоимость\n/записаться — заявка\n/вопрос — вопрос\n\n🔒 Телефон и данные ребёнка собираются только в личном чате.')
 if (m.from_user.username or '').lower()==ADMIN:
  put('admin_chat_id',str(m.chat.id)); return await m.answer('✅ Вы зарегистрированы. Новые заявки будут приходить сюда.',reply_markup=menu())
 await m.answer('<b>Здравствуйте! Это CoolClass 👋</b>\n\nСемейная школа во Внуково, 1–5 классы, группы 7–9 детей, математический уклон.\n\nВыберите раздел:',reply_markup=menu())

async def schedule(m): await m.answer('🕘 <b>Расписание</b>\n\nПонедельник–пятница\n<b>09:00–18:00</b>')
async def price(m): await m.answer('💰 <b>Стоимость</b>\n\n<b>65 000 ₽ в месяц</b>\n\nВсё включено, в том числе <b>трёхразовое питание</b>.')
async def signup(m): await m.answer('🎓 <b>Заявка</b>\n\nОткройте личный чат с @CoolclassVnukovobot и нажмите Start. Личные данные собираются только там.')
async def question_info(m): await m.answer('❓ Задайте вопрос в личном чате с @CoolclassVnukovobot — так контактные данные останутся приватными.')

@dp.message(lambda m: group(m) and cmd(m.text) in {'/расписание','/schedule'})
async def gs(m): await schedule(m)
@dp.message(lambda m: group(m) and cmd(m.text) in {'/стоимость','/price'})
async def gp(m): await price(m)
@dp.message(lambda m: group(m) and cmd(m.text) in {'/записаться','/signup'})
async def gu(m): await signup(m)
@dp.message(lambda m: group(m) and cmd(m.text) in {'/вопрос','/question'})
async def gq(m): await question_info(m)
@dp.message(lambda m: group(m) and (m.text or '').strip().lower() in {'расписание','стоимость','записаться','вопрос'})
async def gt(m):
 t=(m.text or '').strip().lower(); return await {'расписание':schedule,'стоимость':price,'записаться':signup,'вопрос':question_info}[t](m)
@dp.message(lambda m: group(m) and bool(m.text))
async def fallback(m): await m.answer('🤖 Я на связи. Используйте /расписание, /стоимость, /записаться или /вопрос')

def chcmd(text): return cmd(text)
@dp.channel_post(lambda m: chcmd(m.text) in {'/расписание','/schedule'})
async def cs(m:Message): await schedule(m)
@dp.channel_post(lambda m: chcmd(m.text) in {'/стоимость','/price'})
async def cp(m:Message): await price(m)
@dp.channel_post(lambda m: chcmd(m.text) in {'/записаться','/signup'})
async def cu(m:Message): await signup(m)
@dp.channel_post(lambda m: chcmd(m.text) in {'/вопрос','/question'})
async def cq(m:Message): await question_info(m)

@dp.message(lambda m: not group(m) and m.text=='🏫 О школе')
async def about(m): await m.answer('<b>CoolClass — семейная школа во Внуково</b> 🏫\n\n1–5 классы\nГруппы 7–9 детей\nМатематика каждый день\nАнглийский\nОтдельное здание\nЗакрытая территория\nПрогулки\nТрёхразовое питание включено',reply_markup=menu())
@dp.message(lambda m: not group(m) and m.text=='📚 Программа')
async def program(m): await m.answer('<b>Программа</b> 📚\n\nМатематика каждый день, английский язык, основные предметы, развитие самостоятельности.\n\n1–5 классы.',reply_markup=menu())
@dp.message(lambda m: not group(m) and m.text=='🕘 Расписание')
async def ps(m): await schedule(m)
@dp.message(lambda m: not group(m) and m.text=='💰 Стоимость')
async def pp(m): await price(m)
@dp.message(lambda m: not group(m) and m.text=='📍 Как нас найти')
async def loc(m): await m.answer('<b>CoolClass</b> 📍\n\nМосква, ул. Плотинная, 28\nВнуково\n📞 +7 929 692-92-08',reply_markup=menu())
@dp.message(lambda m: not group(m) and m.text=='🎓 Записаться')
async def begin(m,state): await state.set_state(Lead.parent); await m.answer('Оставьте заявку.\n\n<b>Как вас зовут?</b>',reply_markup=ReplyKeyboardRemove())
@dp.message(Lead.parent)
async def parent(m,state): await state.update_data(parent=m.text or ''); await state.set_state(Lead.child); await m.answer('<b>Возраст или класс ребёнка?</b>')
@dp.message(Lead.child)
async def child(m,state): await state.update_data(child=m.text or ''); await state.set_state(Lead.phone); await m.answer('<b>Номер телефона:</b>',reply_markup=phone_menu())
@dp.message(Lead.phone)
async def phone(m,state):
 p=m.contact.phone_number if m.contact else (m.text or '').strip()
 if len(p)<7: return await m.answer('Пожалуйста, отправьте номер телефона кнопкой ниже.',reply_markup=phone_menu())
 await state.update_data(phone=p); await state.set_state(Lead.interest); await m.answer('<b>Что вас интересует?</b>',reply_markup=interest_menu())
@dp.message(Lead.interest)
async def interest(m,state):
 d=await state.get_data(); d['interest']=m.text or ''; u='@'+m.from_user.username if m.from_user.username else 'нет username'
 await admin('🔔 <b>Новая заявка CoolClass</b>\n\n👤 '+d.get('parent','')+'\n👧 '+d.get('child','')+'\n📞 '+d.get('phone','')+'\n🎯 '+d.get('interest','')+'\n💬 '+u+'\n🕐 '+datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
 await state.clear(); await m.answer('✅ <b>Заявка принята!</b> Менеджер свяжется с вами.',reply_markup=menu())
@dp.message(lambda m: not group(m) and m.text=='❓ Задать вопрос')
async def qstart(m,state): await state.set_state(Lead.question); await m.answer('Напишите ваш вопрос.',reply_markup=ReplyKeyboardRemove())
@dp.message(Lead.question)
async def q(m,state):
 u='@'+m.from_user.username if m.from_user.username else 'нет username'; await admin('❓ <b>Вопрос</b>\n\n'+u+'\n'+(m.text or '')); await state.clear(); await m.answer('Спасибо! Вопрос передан менеджеру.',reply_markup=menu())

async def health(r): return web.json_response({'status':'ok','bot':'CoolClass'})
async def startup(*a,**kw):
 conn().close(); me=await bot.get_me(); log.info('BOT OK @%s id=%s',me.username,me.id)
 await bot.set_my_commands([{'command':'start','description':'Начать'},{'command':'schedule','description':'Расписание'},{'command':'price','description':'Стоимость'},{'command':'signup','description':'Оставить заявку'},{'command':'question','description':'Задать вопрос'}])
 await bot.set_webhook(url=URL+'/webhook',secret_token=SECRET,drop_pending_updates=False,allowed_updates=['message','channel_post'])
 info=await bot.get_webhook_info(); log.info('WEBHOOK=%s pending=%s allowed=%s',info.url,info.pending_update_count,info.allowed_updates)
async def shutdown(*a,**kw): await bot.delete_webhook(drop_pending_updates=False); await bot.session.close()

app=web.Application(); app.router.add_get('/',health); app.router.add_get('/health',health)
handler=SimpleRequestHandler(dispatcher=dp,bot=bot,secret_token=SECRET); handler.register(app,path='/webhook'); setup_application(app,dp,bot=bot)
dp.startup.register(startup); dp.shutdown.register(shutdown)

if __name__=='__main__': web.run_app(app,host='0.0.0.0',port=PORT)
