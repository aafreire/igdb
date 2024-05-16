import json
import subprocess
from datetime import datetime
import argparse
from googletrans import Translator
from tqdm import tqdm

parser = argparse.ArgumentParser(description="Script para recuperar dados da API IGDB e gerar comandos de inserção SQL")
parser.add_argument("--platform", help="Plataforma do jogo")
parser.add_argument("--game_name", help="Nome do jogo")
parser.add_argument("--timestamp", help="Data de criação em formato timestamp")
parser.add_argument("--limit", help="Limite de itens retornados")
parser.add_argument("--service_id", help="ID do serviço")
args = parser.parse_args()

def format_date(date_string):
    if date_string and date_string != 'TBD':
        if 'Q' in date_string:
            quarter, year = date_string.split()
            month = {'Q1': 'Jan', 'Q2': 'Apr', 'Q3': 'Jul', 'Q4': 'Oct'}[quarter]
            return f"{month} 01, {year}"
        elif len(date_string) == 4:
            return f"Jan 01, {date_string}"
        else:
            try:
                date_object = datetime.strptime(date_string, '%b %d, %Y')
                return date_object.strftime('%Y-%m-%d')
            except ValueError:
                return date_string
    return ''

def translate_fields(game):
    translator = Translator()

    age_ratings_traduzido = ', '.join([translator.translate(content.get('description', ''), src='en', dest='pt').text for rating in game.get('age_ratings', []) for content in rating.get('content_descriptions', [])])

    summary_text = game.get('summary', '')
    description_traduzido = ''
    if summary_text:
        description_traduzido = translator.translate(summary_text, src='en', dest='pt').text

    release_date = format_date(game.get('release_dates', [{}])[0].get('human', ''))

    game_modes = [mode['name'] for mode in game.get('game_modes', [])]

    languages = []
    language_supports = game.get('language_supports')
    if language_supports:

        unique_languages = set()
        for language in language_supports:
            lang_name = language['language']['name']

            if lang_name not in unique_languages:
                languages.append(lang_name)
                unique_languages.add(lang_name)

    pre_sale = game.get('status', '') == 'pre_sale'

    return {
        'text_button': '',
        'link': '',
        'label_link': '',
        'release_date': release_date,
        'technical_specifications': {
            'age_ratings': age_ratings_traduzido,
            'company': game.get('involved_companies', [{}])[0].get('company', {}).get('name', ''),
            'developed': game.get('involved_companies', [{}])[0].get('name', ''),
            'game_modes': game_modes
        },
        'activation_description': '',
        'parental_rating': '14',
        'pre_sale': pre_sale,
        'languages': languages,
        'steps': [''],
        'description': description_traduzido
    }

output_file = 'insert_commands.sql'

curl_command_base = "curl 'https://api.igdb.com/v4/games' -d 'fields name,cover.url,screenshots.url,genres.name,release_dates.human,status,videos.video_id,language_supports.language.name,summary,platforms.*,platforms.platform_logo.url,involved_companies.company.name,game_modes.*,multiplayer_modes.*,age_ratings.content_descriptions.description"

curl_command_filters = ""
if args.platform:
    curl_command_filters += ";where platforms = " + args.platform
if args.game_name:
    curl_command_filters += ";search '" + args.game_name + "'"
if args.timestamp:
    curl_command_filters += ";where date < " + args.timestamp
if args.limit:
    curl_command_filters += ";limit " + args.limit

if curl_command_filters:
    curl_command_filters += ";"

curl_command = curl_command_base + curl_command_filters + "' -H 'Client-ID: o8y8b5gzc63jat5pajuxjxn1wq22n1' -H 'Authorization: Bearer lwn0qazmvpp3oqxwer6hni1usewe2u' -H 'Accept: application/json' | jq -c ."

curl_output = subprocess.check_output(curl_command, shell=True).decode('utf-8')

games = json.loads(curl_output)

with open(output_file, 'w') as f:
    for game in tqdm(games, desc="Gerando comandos", bar_format="{l_bar}{bar:10}{r_bar}"):

        translated_fields = translate_fields(game)

        game_id = game.get('id')
        game_name = game.get('name')
        if game_name:
            game_name = game_name.replace("'", "''")
        else:
            game_name = 'Unknown'

        cover_url = game.get('cover', {}).get('url', '')

        release_dates = game.get('release_dates', [])
        release_date = format_date(release_dates[0].get('human', '')) if release_dates else ''

        pre_sale = game.get('status', '') == 'pre_sale'

        if cover_url:
            cover_suffix = cover_url.split('//images.igdb.com/igdb/image/upload/t_thumb/')[1]
            image_links = {
                'logo': "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/" + cover_suffix,
                'card_web': "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/" + cover_suffix,
                'selected_image': "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/" + cover_suffix,
                'game_cover': "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/" + cover_suffix,
                'background': {
                    'desktop': "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/" + cover_suffix,
                    'mobile': "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/" + cover_suffix
                }
            }
        else:
            image_links = {
                'logo': '',
                'card_web': '',
                'selected_image': '',
                'game_cover': '',
                'background': {
                    'desktop': '',
                    'mobile': ''
                }
            }

        files_links = [f"{{\"type\": \"image\", \"link\": \"https://images.igdb.com/igdb/image/upload/t_cover_big_2x/{file['url'].split('/')[-1]}\"}}" for file in game.get('screenshots', [])]

        platforms_links = [f"{{\"link\": \"{platform['platform_logo']['url']}\", \"platform\": \"{platform['name']}\"}}" for platform in game.get('platforms', [])]

        involved_companies = game.get('involved_companies', [{}])
        company_name = involved_companies[0].get('company', {}).get('name', '')

        insert_command = f"""
            INSERT INTO service (
                id,
                name,
                service_type_id,
                price,
                service_code,
                url,
                description,
                images,
                active,
                created_at,
                updated_at,
                credit_type_id,
                color,
                external_id,
                has_stock,
                service_id,
                is_license,
                marketplace_visible,
                sale_price
            ) VALUES (
                uuid_generate_v4(),
                '{game_name}',
                '2abbd16c-e745-4c8a-a247-2fe1a76f4343',
                0000,
                'code',
                '{translated_fields.get('url', '')}',
                '{json.dumps(translated_fields)}',
                '{{
                    "logo": "{image_links['logo']}",
                    "card_web": "{image_links['card_web']}",
                    "selected_image": "{image_links['selected_image']}",
                    "game_cover": "{image_links['game_cover']}",
                    "background": {{
                        "desktop": "{image_links['background']['desktop']}",
                        "mobile": "{image_links['background']['mobile']}"
                    }},
                    "files": [{', '.join(files_links)}],
                    "platforms": [{', '.join(platforms_links)}]
                }}',
                true,
                NOW(),
                NOW(),
                '582a1a27-09ed-46c9-b4fa-7fe1688a7839',
                NULL,
                NULL,
                true,
                '{args.service_id}',
                false,
                false,
                NULL
            );
        """

        f.write(insert_command)

print(f"Os comandos de inserção foram salvos em '{output_file}'.")
