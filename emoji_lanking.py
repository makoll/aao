import argparse
import json
import os
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from functools import reduce
from operator import add

import requests
import slackweb
import yaml


def merge_dict_add_values(dict_list):
    return dict(reduce(lambda d1, d2: Counter(d1) + Counter(d2), dict_list))


def parser():
    _parser = argparse.ArgumentParser(description='Slackえもじカウンター')
    _parser.add_argument('-d', '--days', help='何日まえからの取得とするか')

    return _parser


def get_args():
    args = sys.argv[1:]
    _parser = parser()
    return _parser.parse_args(args)


def get_slack_info():
    slack_info_file = os.path.dirname(__file__) + 'config/private/slack.yaml'
    f = open(slack_info_file, 'r')
    return yaml.load(f)


slack_info = get_slack_info()
slack_api_params_base = {
    'token': slack_info.get('token'),
}


def execute_api(api, params):
    api += '&'.join(['%s={%s}' % (k, k) for k in params.keys()])
    url = api.format(**params)
    # print(13, url)
    r = requests.get(url)
    return json.loads(r.text)


def notify_slack(text: str) -> None:
    """Slackに送信する

    Args:
        text (str)    : Slackに送信するメッセージ
        webhook_params (dict) : Slackへの送信に必要なパラメータ

        paramsは以下のkey-valueの情報を含む
            channel (str)    : 送信先チャンネル名
            url (str)        : 送信先チャンネル用のwebhookURL
            username (str)   : 送信メッセージに表示される送信者名
            icon_emoji (str) : 送信メッセージに表示されるアイコン画像

    Returns:
        なし

    """
    if not text:
        text = '絵文字なし'
    webhook_params = slack_info.get('post')

    channel = webhook_params.get('channel')
    url = webhook_params.get('url')
    username = webhook_params.get('username')
    icon_emoji = webhook_params.get('icon_emoji')

    slack = slackweb.Slack(url=url)
    slack.notify(
        text=text,
        channel=channel,
        username=username,
        icon_emoji=icon_emoji,
    )


def get_channel_ids():

    channels_list_api_base = 'https://slack.com/api/channels.list?'
    channels_list = execute_api(channels_list_api_base, slack_api_params_base)
    [print(g['name'], g['id']) for g in channels_list['channels']]
    return [g['id'] for g in channels_list['channels']]


def get_group_ids():

    groups_list_api_base = 'https://slack.com/api/groups.list?'
    groups_list = execute_api(groups_list_api_base, slack_api_params_base)
    # [print(g['name'], g['id']) for g in groups_list['groups']]
    return [g['id'] for g in groups_list['groups']]


def get_messages(group_id, oldest, api_prefix):

    groups_history_api = 'https://slack.com/api/%s.history?' % api_prefix

    groups_history_params = deepcopy(slack_api_params_base)
    groups_history_params.update({
        'channel': group_id,
        'count': 1000,
        'oldest': oldest,
    })
    message_data = execute_api(groups_history_api, groups_history_params)
    # print(33, message_data)

    return message_data['messages'] if message_data and message_data['messages'] else []


def get_emoji(messages, oldest):
    results = {}  # dict

    for m in messages:
        # print(107, m)
        # print(97, m['ts'], oldest, float(m['ts']) < oldest)
        if float(m['ts']) < oldest:
            continue
        for r in m.get('reactions', []):
            name = r['name']
            results[name] = results.get(name, 0) + r['count']

    # print(59, results)
    return results


def exec():

    args = get_args()
    oldest = (datetime.today() - timedelta(days=int(args.days))).timestamp()

    group_ids = get_group_ids()
    # group_ids = []
    # group_ids = group_ids[:10]
    groups_messages_list = [get_messages(group_id, oldest, 'groups') for group_id in group_ids]
    groups_messages = reduce(add, groups_messages_list) if groups_messages_list else []

    channel_ids = get_channel_ids()
    # channel_ids = channel_ids[:10]
    channel_ids = []
    channels_messages_list = [get_messages(channel_id, oldest, 'channels') for channel_id in channel_ids]
    channels_messages = reduce(add, channels_messages_list) if channels_messages_list else []

    messages = groups_messages + channels_messages

    results = get_emoji(messages, oldest)
    results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    # print(results)
    slack_str = ''
    for r in results:
        slack_str += ':%s: %s回\n' % (r[0], r[1])
    notify_slack(slack_str)


exec()

