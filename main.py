import logging
import random
import json
import re
from datetime import datetime
import asyncio
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv
import os

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
CARDS_FILE = os.getenv('CARDS_FILE', './data/cards.json')
LOG_FILE = os.getenv('LOG_FILE', './logs/user_answers.log')
COURSE_NAME = os.getenv('COURSE_NAME')

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Загрузка карточек для самоконтроля
with open(CARDS_FILE, 'r', encoding='utf-8') as f:
    cards = json.load(f)

user_cards = {}
user_history = {}


def escape_markdown(text: str) -> str:
    """
    Экранирует спецсимволы Markdown (версия Telegram MarkdownV1).
    """
    escape_chars = r'\*_`\['
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


def log_answer(user_id, username, question, answer):
    timestamp = datetime.now().isoformat()
    log_entry = {
        "user_id": user_id,
        "username": username,
        "timestamp": timestamp,
        "question": question,
        "answer": answer
    }
    with open(LOG_FILE, 'a', encoding='utf-8') as log_file:
        log_file.write(json.dumps(log_entry, ensure_ascii=False) + '\n')


async def send_random_card(user_id: int, chat_id: int):
    history = user_history.setdefault(user_id, set())

    all_questions = [
        (cat, q, a)
        for cat, qa_list in cards.items()
        for q, a in qa_list
        if (cat, q) not in history
    ]

    if not all_questions:
        await bot.send_message(chat_id, "Ты прошёл все карточки! Напиши /quiz, чтобы начать заново.")
        user_history[user_id].clear()
        return

    category, question, answer = random.choice(all_questions)
    user_cards[user_id] = (category, question, answer)
    user_history[user_id].add((category, question))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Показать ответ", callback_data="show_answer")]
    ])

    await bot.send_message(
        chat_id,
        f"Категория: *{escape_markdown(category)}*\n\n❓ *{escape_markdown(question)}*",
        parse_mode="Markdown",
        reply_markup=kb
    )


@router.message(Command(commands=["start"]))
async def start_command(message: Message):
    await message.answer(f"Привет! Я помогу тебе подготовиться к базовым вопросам по {COURSE_NAME}. Напиши /quiz для начала.")


@router.message(Command(commands=["quiz"]))
async def quiz_command(message: Message):
    await send_random_card(message.from_user.id, message.chat.id)


@router.callback_query(lambda c: c.data == "show_answer")
async def show_answer(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "anonymous"

    if user_id not in user_cards:
        await callback_query.answer("❌ У тебя нет активной карточки!", show_alert=True)
        return

    category, question, answer = user_cards[user_id]
    log_answer(user_id, username, question, answer)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Следующий вопрос", callback_data="next_question")]
    ])

    await bot.send_message(
        user_id,
        f"✅ *Ответ:*\n{escape_markdown(answer)}",
        parse_mode="Markdown",
        reply_markup=kb
    )


@router.callback_query(lambda c: c.data == "next_question")
async def next_question(callback_query: CallbackQuery):
    await send_random_card(callback_query.from_user.id, callback_query.message.chat.id)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
