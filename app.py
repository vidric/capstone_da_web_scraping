from flask import Flask, render_template, redirect, url_for
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from bs4 import BeautifulSoup 
import requests
from datetime import datetime, timedelta
import sqlite3

#don't change this
matplotlib.use('Agg')
app = Flask(__name__) #do not change this

def func_scrape():
	con = sqlite3.connect('kalibrr.db')
	query = con.cursor()

	# Membuat tabel jika belum ada
	query.execute('''CREATE TABLE IF NOT EXISTS job_listing
             (id INTEGER PRIMARY KEY AUTOINCREMENT, title_pekerjaan TEXT, lokasi_pekerjaan TEXT, negara TEXT, tanggal_posting DATE, deadline DATE, perusahaan TEXT,
             UNIQUE(title_pekerjaan, perusahaan))''')

    #ambil jumlah page
	url_get = requests.get('https://www.kalibrr.id/job-board/te/data/1')
	soup = BeautifulSoup(url_get.content,"html.parser")
	last_pagination = soup.find_all('li', class_='k-mx-2')[-1]
	last_page_number = int(last_pagination.find('a').get_text())
	print('Total Page: '+ str(last_page_number))

	temp = [] #initiating a list
	today = datetime.today().date()

	print('Mulai Proses Scraping')
        
	for i in range(1, last_page_number):
		progress = round((i / last_page_number) * 100)
		print(f'Progress: {progress}% | Page {i} dari {last_page_number} Pages', end='\r')


		url = 'https://www.kalibrr.id/job-board/te/data/' + str(i)
		url_get = requests.get(url)
		soup = BeautifulSoup(url_get.content,"html.parser")
		items = soup.find_all("div", {"class": "k-grid k-border-tertiary-ghost-color k-text-sm k-p-4 md:k-p-6 css-1b4vug6"})

		for item in items:
			title_pekerjaan = item.select_one("h2 a").text
			lokasi_pekerjaan = item.select_one("div.k-col-start-3 div.k-flex > a").text.strip().split(",")
			tanggal_post = item.select_one("div.k-col-start-5 span:first-of-type").text.strip().split("•")
			tanggal_posting = tanggal_post[0]
			deadline = tanggal_post[1]
			perusahaan = item.select_one("div.k-col-start-3 span:first-of-type a").text.strip()
			diff = 0

			# convert tanggal posting
			if 'a day ago' in tanggal_posting:
				diff = 1
			elif 'a month ago' in tanggal_posting:
				diff = 30
			
			if 'days ago' in tanggal_posting:
				diff = tanggal_posting.split(' ')[1].strip()
			
			if 'months ago' in tanggal_posting:
				diff = int(tanggal_posting.split(' ')[1].strip()) * 30
			
			tanggal_posting = today - timedelta(days=int(diff))
			# END convert tanggal posting

			# convert deadline
			deadline = deadline[13:].strip() + ' 2023' # default tahun 2023
			tanggal_deadline = datetime.strptime(deadline, '%d %b %Y').strftime('%Y-%m-%d')
			tanggal_deadline = datetime.strptime(tanggal_deadline, '%Y-%m-%d')
			tanggal_deadline = tanggal_deadline.date()
			# END convert deadline

			# convert nama kota
			nama_negara = lokasi_pekerjaan[1].strip()
			nama_kota = lokasi_pekerjaan[0]
			mapping = {'South Jakarta': 'Jakarta Selatan', 'West Jakarta': 'Jakarta Barat', 'North Jakarta': 'Jakarta Utara', 'East Jakarta':'Jakarta Timur', 'Jakarta':'Jakarta Pusat', 'South Tangerang': 'Tangerang Selatan', 'Bandung Kota':'Bandung', 'Bandung Kabupaten':'Bandung', 'Bogor Kota':'Bogor', 'Central Jakarta': 'Jakarta Pusat', 'Central Jakarta City': 'Jakarta Pusat', 'Central Lampung': 'Lampung', 'Kota Jakarta Barat': 'Jakarta Barat', 'Kota Jakarta Pusat':'Jakarta Pusat', 'Kota Jakarta Selatan':'Jakarta Selatan'}
			nama_kota_baru = nama_kota.replace(nama_kota, mapping.get(nama_kota, nama_kota))
			#END convert nama kota

			temp.append((title_pekerjaan, nama_kota_baru, nama_negara, tanggal_posting, tanggal_deadline, perusahaan))

	query.executemany('INSERT OR IGNORE INTO job_listing (title_pekerjaan, lokasi_pekerjaan, negara, tanggal_posting, deadline, perusahaan) VALUES (?, ?, ?, ?, ?, ?)', temp)
	con.commit()
	con.close()

def func_empty_db():
	con = sqlite3.connect('kalibrr.db')
	query = con.cursor()
	query.execute('DELETE FROM job_listing')
	con.commit()
	con.close()

# Fungsi untuk membuat plot
def create_plot(data):
    if data.empty:
        return None
    
    ax = data.plot(kind='bar', figsize = (20,9)) 
    figfile = BytesIO()
    plt.savefig(figfile, format='png', transparent=True)
    figfile.seek(0)
    figdata_png = base64.b64encode(figfile.getvalue())
    plt.close()
    return str(figdata_png)[2:-1] 
# END Fungsi membuat plot

@app.route('/scrap', methods=['POST'])
def run_my_function():
    func_scrape()
    return redirect(url_for('index'))

@app.route('/delete', methods=['POST'])
def run_my_function_delete():
    func_empty_db()
    return redirect(url_for('index'))

@app.route("/")
def index(): 

	conn = sqlite3.connect("kalibrr.db")
	data = pd.read_sql_query("SELECT * FROM job_listing", conn)

	if data.empty:
		data_grouped = pd.DataFrame()
		data_grouped_month = pd.DataFrame()
		data_dict = []
		total_baris = 0
	else:
		#insert data wrangling here
		data = pd.read_sql_query("SELECT * FROM job_listing", conn)
		data_indonesia = data[data['negara'] == 'Indonesia']
		data_grouped = data_indonesia['lokasi_pekerjaan'].value_counts()

		data_indonesia['tanggal_posting'] = pd.to_datetime(data_indonesia['tanggal_posting'])
		data_indonesia['year_month'] = data_indonesia['tanggal_posting'].dt.to_period('M')
		data_grouped_month = data_indonesia['year_month'].value_counts()
		#end of data wranggling
		data_dict = data.to_dict('records')
		total_baris = len(data_dict)

	plot_result = create_plot(data_grouped)
	plot_result_month = create_plot(data_grouped_month)

	# render to html
	return render_template('index.html',
		plot_result=plot_result,
		plot_result_month=plot_result_month,
		data_scrap = data_dict,
		total_baris = total_baris
		)

if __name__ == "__main__": 
    app.run(debug=True)
	