from market_tracker import run_update

if __name__ == "__main__":
    for message in run_update():
        print(message)
