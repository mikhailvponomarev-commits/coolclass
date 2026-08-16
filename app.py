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