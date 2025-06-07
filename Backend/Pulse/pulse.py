from tpulse import TinkoffPulse
from pprint import pp

pulse = TinkoffPulse()

user_info = pulse.get_user_info("T-Investments")
user_posts = pulse.get_posts_by_user_id(user_info["id"])  # все посты определенного канала
pp(user_posts)

ticker_posts = pulse.get_posts_by_ticker("SBER")  # все новости по тикеру
pp(ticker_posts["items"][:5])  # последние 5 новостей по этому тикеру