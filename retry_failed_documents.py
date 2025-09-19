import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os
import re
from urllib.parse import quote
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('retry_failed_documents.log'),
        logging.StreamHandler()
    ]
)

class RetryFailedDocuments:
    def __init__(self, output_dir='normativos_txt', debug=True):
        self.output_dir = output_dir
        self.debug = debug
        self.driver = None
        self.wait = None
        
        # Criar diretório de saída
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(f"{self.output_dir}/normativos_pdf").mkdir(parents=True, exist_ok=True)
        
        # Configurar Selenium WebDriver
        self._setup_driver(headless=not debug)

    def _setup_driver(self, headless=True):
        """Configura o WebDriver do Selenium"""
        try:
            # Configurações do Chrome para evitar detecção de bot
            chrome_options = Options()
            
            # Modo headless (configurável)
            if headless:
                chrome_options.add_argument('--headless=new')
            
            # Configurações para evitar detecção
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Desabilitar imagens para acelerar o carregamento
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Inicializar o driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Executar script para remover propriedades de automação
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Configurar timeout
            self.wait = WebDriverWait(self.driver, 20)
            
            logging.info("WebDriver configurado com sucesso")
            
        except Exception as e:
            logging.error(f"Erro ao configurar WebDriver: {e}")
            raise

    def access_document(self, document_url, document_type, document_number):
        """Acessa o documento usando URL do CSV"""
        try:
            logging.info(f"Acessando documento: {document_url}")
            
            # Navegar para a URL do documento
            self.driver.get(document_url)
            time.sleep(5)  # Aguardar mais tempo para carregar
            
            if self.debug:
                logging.info(f"Página carregada: {self.driver.title}")
                self.driver.save_screenshot(f"debug_retry_{document_number}.png")
                logging.info(f"Screenshot salvo: debug_retry_{document_number}.png")
            
            # Verificar se a página carregou corretamente
            if "exibenormativo" in self.driver.current_url:
                return True
            else:
                logging.warning(f"URL não funcionou: {self.driver.current_url}")
                return False
                
        except Exception as e:
            logging.error(f"Erro ao acessar documento {document_type} {document_number}: {e}")
            return False

    def scrape_document_content(self, document_type, document_number, document_date):
        """Extrai o conteúdo do documento carregado com seletores mais abrangentes"""
        try:
            # Aguardar o conteúdo do documento carregar
            time.sleep(3)
            
            # Tentar diferentes seletores para o conteúdo do documento
            content_selectors = [
                ".documento-conteudo",
                ".normativo-conteudo", 
                ".conteudo-documento",
                ".document-content",
                "#conteudo",
                ".main-content",
                "main",
                ".container .row",
                ".row .col-md-12",
                ".row .col-lg-12",
                ".row .col-sm-12",
                ".row .col",
                ".content",
                ".text",
                ".document",
                "article",
                ".normativo",
                ".resolucao",
                ".circular"
            ]
            
            content_element = None
            for selector in content_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element and element.text.strip() and len(element.text.strip()) > 100:
                            content_element = element
                            logging.info(f"Conteúdo encontrado com seletor: {selector}")
                            break
                    if content_element:
                        break
                except NoSuchElementException:
                    continue
            
            if not content_element:
                # Se não encontrar conteúdo específico, usar o body
                content_element = self.driver.find_element(By.TAG_NAME, "body")
                logging.info("Usando body como fallback")
            
            # Extrair texto
            content_text = content_element.text
            
            if not content_text.strip():
                logging.warning(f"Conteúdo vazio para {document_type} {document_number}")
                # Tentar extrair HTML como fallback
                content_html = content_element.get_attribute('innerHTML')
                if content_html and len(content_html.strip()) > 100:
                    logging.info("Tentando extrair HTML como fallback")
                    soup = BeautifulSoup(content_html, 'html.parser')
                    content_text = soup.get_text()
            
            if not content_text.strip():
                logging.warning(f"Conteúdo ainda vazio para {document_type} {document_number}")
                return None
            
            # Salvar como arquivo de texto
            filename = f"{document_type.replace(' ', '_')}_{document_number}_{document_date.replace('/', '_')}.txt"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Tipo: {document_type}\n")
                f.write(f"Número: {document_number}\n")
                f.write(f"Data: {document_date}\n")
                f.write(f"URL: {self.driver.current_url}\n")
                f.write("="*80 + "\n\n")
                f.write(content_text)
            
            logging.info(f"Conteúdo salvo: {filepath}")
            
            # Tentar baixar PDF se disponível
            self._download_pdf(document_type, document_number, document_date)
            
            return filepath
            
        except Exception as e:
            logging.error(f"Erro ao extrair conteúdo do documento {document_type} {document_number}: {e}")
            return None

    def _download_pdf(self, document_type, document_number, document_date):
        """Tenta baixar o PDF do documento"""
        try:
            # Procurar por links de PDF
            pdf_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='.pdf'], a[href*='download']")
            
            for link in pdf_links:
                href = link.get_attribute('href')
                if href and '.pdf' in href.lower():
                    # Baixar o PDF
                    response = requests.get(href, timeout=30)
                    if response.status_code == 200:
                        pdf_filename = f"{document_type.replace(' ', '_')}_{document_number}_{document_date.replace('/', '_')}.pdf"
                        pdf_filepath = os.path.join(self.output_dir, "normativos_pdf", pdf_filename)
                        
                        with open(pdf_filepath, 'wb') as f:
                            f.write(response.content)
                        
                        logging.info(f"PDF baixado: {pdf_filepath}")
                        break
                        
        except Exception as e:
            logging.warning(f"Erro ao baixar PDF para {document_type} {document_number}: {e}")

    def process_failed_documents(self):
        """Processa apenas os documentos que falharam"""
        # Documentos que falharam
        failed_documents = [
            {
                'tipo': 'Resolucao CMN',
                'numero': '4.734',
                'data': '27/6/2019',
                'url_bcb': 'https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&numero=4.734'
            },
            {
                'tipo': 'Resolucao CMN',
                'numero': '4.282',
                'data': '4/11/2013',
                'url_bcb': 'https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&numero=4.282'
            }
        ]
        
        total_docs = len(failed_documents)
        successful_docs = 0
        failed_docs = 0
        
        logging.info(f"Tentando reprocessar {total_docs} documentos que falharam")
        
        for index, doc in enumerate(failed_documents):
            try:
                document_type = doc['tipo']
                document_number = doc['numero']
                document_date = doc['data']
                document_url = doc['url_bcb']
                
                logging.info(f"Reprocessando {index + 1}/{total_docs}: {document_type} {document_number}")
                
                # Acessar o documento usando URL do CSV
                if self.access_document(document_url, document_type, document_number):
                    # Extrair conteúdo
                    result = self.scrape_document_content(document_type, document_number, document_date)
                    if result:
                        successful_docs += 1
                        logging.info(f"✓ Documento reprocessado com sucesso: {document_type} {document_number}")
                    else:
                        failed_docs += 1
                        logging.error(f"✗ Falha ao extrair conteúdo: {document_type} {document_number}")
                else:
                    failed_docs += 1
                    logging.error(f"✗ Falha ao acessar documento: {document_type} {document_number}")
                
                # Pausa entre requisições para evitar bloqueio
                time.sleep(3)
                
            except Exception as e:
                failed_docs += 1
                logging.error(f"Erro ao reprocessar documento {index + 1}: {e}")
                continue
        
        logging.info(f"Reprocessamento concluído. Sucessos: {successful_docs}, Falhas: {failed_docs}")

    def close(self):
        """Fecha o driver"""
        if self.driver:
            self.driver.quit()
            logging.info("WebDriver fechado")

def main():
    """Função principal"""
    scraper = None
    try:
        # Criar instância do scraper
        scraper = RetryFailedDocuments(debug=True)
        
        # Reprocessar documentos que falharam
        scraper.process_failed_documents()
        
    except KeyboardInterrupt:
        logging.info("Reprocessamento interrompido pelo usuário")
    except Exception as e:
        logging.error(f"Erro na execução: {e}")
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
