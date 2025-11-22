import datetime


def get_current_time_formatted():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S").lstrip().ljust(19)
