import requests
import re
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from datetime import datetime
from datetime import timedelta
from typing import List, Optional
import json
import pandas as pd


# функция поиска ссылок
def get_links() -> list:
    url = 'https://www.gismeteo.ru/'
    session = requests.session()
    ua = UserAgent(verify_ssl=False)
    req = session.get(url, headers={'User-Agent': ua.chrome})
    html = req.text
    soup = BeautifulSoup(html, 'html.parser')

    links_block = soup.find_all(id="noscript")

    temp_links = []
    for temp_link in links_block:
        temp_links = re.findall('href="(.+?)"', str(temp_link))

    links = []
    for link in temp_links:
        new_link = 'https://www.gismeteo.ru' + link + '10-days/'
        links.append(new_link)

    return links


# достает название города
def get_city(soup: BeautifulSoup) -> str:
    city_html = soup.select("span.locality span")
    city = city_html[0].attrs["title"]
    return city


# достает характеристику погоды ("облачно")
def get_summaries(soup: BeautifulSoup) -> list:
    summary_html = soup.find_all("span", attrs={'class': 'tooltip'})
    summaries = []
    for i in range(10):
        summary = summary_html[i].get("data-text")
        summaries.append(summary)
    return summaries


# заменет знак тире на знак минуса, иначе не получается превратить в int
def transform_minus(number: str) -> int:
    if '−' in number:
        number = number.replace('−', '-')
    return int(number)


# достает макс/мин температуры
def get_temps(soup: BeautifulSoup) -> tuple[list[Optional[int]], list[Optional[int]]]:
    data_html = soup.find_all(attrs={'class': 'values'})
    temp_html = data_html[0]
    max_temps = []
    min_temps = []

    for line in temp_html:
        line = str(line)
        if '<div class="maxt">' in line:
            max_temp = re.findall('unit_temperature_c">(.+?)</span>', line)
            max_temp = transform_minus(max_temp[0])
            max_temps.append(max_temp)
        else:
            # добавляю строку с нан, потому что далее при доставании ср темп с обычным наном
            # работать очень неудобно
            max_temps.append(None)

        if '<div class="mint">' in line:
            min_temp = re.findall('unit_temperature_c">(.+?)</span>', line)
            min_temp = transform_minus(min_temp[1])
            min_temps.append(min_temp)
        else:
            min_temps.append(None)

        if '<div class="mint">' in line and '<div class="maxt">' not in line:
            min_temp = re.findall('unit_temperature_c">(.+?)</span>', line)
            min_temp = transform_minus(min_temp[1])
            min_temps.append(min_temp)  # это на случай, если будет только мин temp
            # не знаю, бывает ли так, но я перестрахуюсь
    return max_temps, min_temps


# достает показатель давления
def get_press(soup: BeautifulSoup) -> tuple[list[Optional[int]], list[Optional[int]]]:
    data_html = soup.find_all(attrs={'class': 'values'})
    pres_html = data_html[-1]
    max_pressures = []
    min_pressures = []

    for line in pres_html:
        line = str(line)
        if '<div class="maxt">' in line:
            max_pressure = re.findall('unit_pressure_mm_hg_atm">(.+?)</span>', line)
            max_pressures.append(int(max_pressure[0]))
        else:
            max_pressures.append(None)

        if '<div class="mint">' in line:
            min_pressure = re.findall('unit_pressure_mm_hg_atm">(.+?)</span>', line)
            min_pressures.append(int(min_pressure[1]))
        else:
            min_pressures.append(None)

        if '<div class="mint">' in line and '<div class="maxt">' not in line:
            min_pressure = re.findall('unit_pressure_mm_hg_atm">(.+?)</span>', line)
            min_pressures.append(int(min_pressure[0]))  # это на случай, если будет только мин давление
            # не знаю, бывает ли так, но я перестрахуюсь
    return max_pressures, min_pressures


# достает показатели осадков
def get_precipitations(soup: BeautifulSoup) -> List[int]:
    precipitation_html = soup.find_all('div', {'class': 'w_prec__value'})
    temp_precipitation = re.findall('">(.+?)</div>', str(precipitation_html), re.DOTALL)
    precipitations = []
    for el in temp_precipitation:  # через обычную регулярку с (\d.+) у меня почему-то не искало
        prec = re.findall(r'\d|,', el)
        if len(prec) > 1:
            prec[-2] = '.'
            prec = ''.join(prec)
            precipitations.append(float(prec))
        else:
            precipitations.append(int(prec[0]))

    return precipitations


# достает показатель силы ветра
def get_max_wind_speed(soup: BeautifulSoup) -> List[int]:
    max_wind_speeds = []
    max_wind_speed_html = soup.select("span.unit_wind_m_s")
    for line in max_wind_speed_html:
        line = str(line)
        if 'unit unit_wind_m_s' in line:
            speed = re.findall(r'\d+', line)
            max_wind_speeds.append(int(speed[0]))
            if len(max_wind_speeds) == 10:
                break

    return max_wind_speeds


# запускает все функции, которые достают данные
# и создает список словарей, который содержит все данные
# о погоде для одного города на 10 дней
def load_forecast(link: str) -> List[dict]:
    url = link
    session = requests.session()
    ua = UserAgent(verify_ssl=False)
    req = session.get(url, headers={'User-Agent': ua.chrome})
    html = req.text
    soup = BeautifulSoup(html, 'html.parser')

    city = get_city(soup)
    summaries = get_summaries(soup)
    temps = get_temps(soup)
    pressures = get_press(soup)
    max_wind_speeds = get_max_wind_speed(soup)
    precipitations = get_precipitations(soup)

    # структура словаря для наглядности
    d = {
        'date': str,
        'city': str,
        'summary': str,
        'max_temp': int or str,
        'min_temp': int or str,
        'max_wind_speed': int,
        'precipitation': int,
        'min_pressure': int or str,
        'max_pressure': int or str,
    }

    l_forecast = []
    for n in range(10):
        date = datetime.now() + timedelta(days=n)
        date = date.strftime("%Y-%m-%d"),

        d = {
            'date': date[0],
            'city': city,
            'summary': summaries[n],
            'max_temp': temps[0][n],
            'min_temp': temps[1][n],
            'max_wind_speed': max_wind_speeds[n],
            'precipitation': precipitations[n],
            'max_pressure': pressures[0][n],
            'min_pressure': pressures[1][n]
        }
        l_forecast.append(d)

    return l_forecast


# создает словарь с прогнозами load_forecast для 10 городов
def load_all_forecasts() -> List[dict]:
    links = get_links()
    del links[10:]

    forecasts = []
    for link in links:
        city_forecast = load_forecast(link)
        for day in city_forecast:
            forecasts.append(day)
    return forecasts


# преобразует даты в datetime объект и создает дни недели в дф
def transform_date_week(df1: pd.DataFrame) -> pd.DataFrame:
    datetimes = pd.to_datetime(df1["date"])
    df1["date"] = datetimes
    df1['day_of_week'] = df1['date'].dt.dayofweek
    return df1


# скользящее среднее арифметическое максимальной температуры с шириной окна в 3 дня
def get_rolls(df1: pd.DataFrame) -> pd.DataFrame:
    i = 0
    rolls_temps = []
    for n in range(10):
        rolling_df = df1[i:i + 10]
        i += 10
        roll = rolling_df['max_temp'].rolling(3).mean()
        rolls_temps.append(roll)

    rolls_for_city = []
    for roll in rolls_temps:
        for temp in roll:
            rolls_for_city.append(temp)

    df1['max_temp_rolling'] = rolls_for_city
    return df1


# считает среднюю температуру за день
def get_aver_temp(df1: pd.DataFrame) -> pd.DataFrame:
    max_df = df1
    average_temps = []
    for index, row in max_df.iterrows():
        if row['min_temp'] is None:
            average_temps.append((row['max_temp'] + row['max_temp']) / 2)

        else:
            average_temps.append((row['max_temp'] + row['min_temp']) / 2)

    max_df['average_temp'] = [i for i in average_temps]

    return max_df


# считает среднюю температуру за два дня
def find_best_city(df1: pd.DataFrame) -> str:
    max_df = get_aver_temp(df1)
    highest_temp = {}
    weekends = []
    for ind, day in enumerate(max_df['day_of_week']):
        if len(weekends) > 0:  # обход того, что вначале список пустой
            weekends.append((ind, day))
            # если предыдущий день недели равен субботе
            if weekends[-2][1] == 5:  # я сначала добавляю день, поэтому для позапрошлого надо брать -2
                aver_w_temp = (max_df['average_temp'][weekends[ind - 1][0]] + max_df['average_temp'][ind]) / 2
                highest_temp[max_df['city'][ind]] = aver_w_temp

        else:
            weekends.append((ind, day))

    highest_temp = dict(sorted(highest_temp.items(), key=lambda item: item[1]))

    return list(highest_temp.keys())[-1]


# получает код города, в который мы хотим поехать
def get_iata(IATA: str) -> str:
    url = 'https://www.travelpayouts.com/widgets_suggest_params?q=Из%20Москвы%20в%20' + IATA
    session = requests.session()
    req = session.get(url, stream=True)
    html = req.text
    iata = json.loads(html)
    iata = iata['destination']['iata']
    return iata


# создает дату ближайшей субботы
def get_saturday() -> str:
    date = datetime.now()
    while date.weekday() != 5:
        date += timedelta(days=1)
    date = date.strftime("%Y-%m-%d")
    return date


# ищёт самый дешевый билет
def find_cheapest_ticket(city: str) -> dict:
    iata = get_iata(city)
    date = get_saturday()
    params = {
        'origin': 'MOW',
        'destination': iata,
        'depart_date': date,  # баг апи, не учитывает дату при отправлении, бака
        'one_way': 'true'
    }
    av_response = requests.get('https://min-prices.aviasales.ru/calendar_preload', params=params)

    tickets = av_response.text
    tickets = json.loads(tickets)

    bests = []
    for i in tickets['best_prices']:
        if i['depart_date'] == str(date):
            bests.append(i['value'])

    bests_sorted = sorted(bests)
    best = {'price': bests_sorted[-1]}

    if len(bests) == 0:
        bests.append('No tickets, sorry')
        best = {'error_text': bests}

    return best


if __name__ == '__main__':
    frcs = load_all_forecasts()
    df = pd.DataFrame(frcs)
    df = transform_date_week(df)
    df = get_rolls(df)
    best_city = find_best_city(df)
    ticket = find_cheapest_ticket(best_city)
    if len(ticket) != 0:
        print('Можно свалить в город ' + best_city + " за " + str(ticket['price']) + ' рубасов')
    else:
        print('Лучше всего свалить в город ' + best_city + ', но билетов нет')
