import requests
import threading
from queue import Queue
import urllib3
from pyuseragents import random as random_useragent

urllib3.disable_warnings()

authorization_header = 'Authorization'
authorization_token = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3N1ZXIiOiJkaWQ6ZXRocjoweGJBN0YzODYxNTNmODgxMTg4NDA0RjgzZjBiRGYxNDFDMjlBN2Y4OUIiLCJwdWJsaWNBZGRyZXNzIjoiMHhiQTdGMzg2MTUzZjg4MTE4ODQwNEY4M2YwYkRmMTQxQzI5QTdmODlCIiwiZW1haWwiOiJzYXRhbmF0cm95QGdtYWlsLmNvbSIsIm9hdXRoUHJvdmlkZXIiOm51bGwsInBob25lTnVtYmVyIjpudWxsLCJ3YWxsZXRzIjpbXSwic2FjSWQiOiI1NmI0MTEyMS1lMTg1LTQzMWMtOTFjZi0zY2JhZDM1MTJjNDIiLCJleHAiOjE3MTI0NzU4MTgsImlzU3Vic2NyaWJlZCI6dHJ1ZSwiaWF0IjoxNzExMjY2MjE4fQ.OfRU4_xWRtfpVy_QmdG22lJoP7AndEuvXnlEABr7i3o'
api_key = 'aca4d876-a68b-4a8b-ad9c-702a14c2b3ba'
api_key_header = 'X-Api-Key'
api_url = 'https://sac-api.solworks.dev/addresses/subscribed'
address_file = 'address.txt'
result_file = 'results.txt'
chunk_size = 100

def load_proxies(fp="proxies.txt"):
    with open(fp, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                proxy_pool.append(f"http://{line}")
    if not proxy_pool:
        raise Exception("No proxies loaded from the file.")
    print(f"{len(proxy_pool)} proxies loaded successfully!")

class PrintThread(threading.Thread):
    def __init__(self, queue, file):
        threading.Thread.__init__(self)
        self.queue = queue
        self.file = file

    def printfiles(self, filename: str, chunk):
        global completed_addresses, total_addresses
        completed_addresses += len(chunk)
        print(f"Completed {completed_addresses} out of {total_addresses}, Remaining: {total_addresses - completed_addresses} addresses")
        with open(filename, "a", encoding="utf-8") as file:
            for address in chunk:
                file.write(address)

    def run(self):
        while True:
            chunk = self.queue.get()
            self.printfiles(self.file, chunk)
            self.queue.task_done()

class ProcessThread(threading.Thread):
    def __init__(self, in_queue, out_queue):
        threading.Thread.__init__(self)
        self.in_queue = in_queue
        self.out_queue = out_queue

    def run(self):
        while True:
            chunk = self.in_queue.get()
            response = self.fetch_data(chunk)
            if response != "": self.out_queue.put(response)
            self.in_queue.task_done()

    def format_entry(self, entry):
        formatted_entry = f"Address:  {entry['address']}\n"
        for el in entry['eligibility']:
            if el['eligible']:
                formatted_entry += f"{(el['protocol'].capitalize()+':').ljust(13)}✅ | Tokens: {el['amount']}💲\n"
            else:
                formatted_entry += f"{(el['protocol'].capitalize()+':').ljust(13)}❌ | Tokens: N/A\n"
        for points in entry['points']:
            if points['points'] > 0:
                formatted_entry += f"{(points['protocol'].capitalize()+':').ljust(13)}✅ | Tokens: {points['points']}💲\n"
            else:
                formatted_entry += f"{(points['protocol'].capitalize()+':').ljust(13)}❌ | Tokens: {points['points']}💲\n"
        return formatted_entry + "\n------------------------------------------------------------------\n\n"
    
    def fetch_data(self, chunk):
        while True:
            try:
                with proxy_pool_lock:
                    if proxy_pool:
                        selected_proxy = proxy_pool.pop(0)
                    else:
                        print("Proxy pool is empty")
                        continue

                sess = requests.session()
                sess.proxies = {'http': selected_proxy, 'https': selected_proxy}
                sess.headers = {
                    'User-Agent': random_useragent(),
                    'Accept-Encoding': 'gzip, deflate',
                    'Accept': '*/*',
                    'Connection': 'keep-alive',
                    api_key_header: api_key,
                    authorization_header: authorization_token
                }
                sess.verify = True
                response = sess.get(api_url, params={"addresses": ','.join(chunk)})
                if response.status_code == 200:
                    # print(f"Chunk processed successfully: {chunk}")
                    return [self.format_entry(entry) for entry in response.json()]
                print(f'Request failed with status code {response.status_code}. Повтор запроса с другим прокси..\n')
                continue

            except Exception as e:
                print(f'Error: {e}. Повтор запроса с другим прокси..\n')
                pass

            finally:
                with proxy_pool_lock:
                    proxy_pool.append(selected_proxy)

proxy_pool = []
proxy_pool_lock = threading.Lock()

total_addresses = 0
completed_addresses = 0

load_proxies()

with open(address_file, 'r', encoding='utf-8') as file:
    addresses = [line.strip() for line in file if line.strip()]
total_addresses = len(addresses)
chunks = [addresses[i:i + chunk_size] for i in range(0, len(addresses), chunk_size)]
print(f'{total_addresses} addresses loaded sucessfully! ({len(chunks)} chunks)')

threads = int(input('Max threads (должно быть не больше количества прокси): '))
# threads = 1

print('started')

pathqueue = Queue()
resultqueue = Queue()

for i in range(0, threads):
    t = ProcessThread(pathqueue, resultqueue)
    t.daemon = True
    t.start()

t = PrintThread(resultqueue, result_file)
t.daemon = True
t.start()

for chunk in chunks:
    pathqueue.put(chunk)

pathqueue.join()
resultqueue.join()