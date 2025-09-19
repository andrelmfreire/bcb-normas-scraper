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
        logging.FileHandler('bcb_official_search_scraper.log'),
        logging.StreamHandler()
    ]
)

class BCBOfficialSearchScraper:
    def __init__(self, csv_file='normativos_spb_bcb.csv', output_dir='normativos_txt', debug=False):
        self.csv_file = csv_file
        self.output_dir = output_dir
        self.debug = debug
        self.driver = None
        self.wait = None
        self.base_url = "https://www.bcb.gov.br/estabilidadefinanceira/buscanormas"
        
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

    def search_document(self, document_number, document_type):
        """Busca um documento específico usando o formulário oficial do BCB"""
        try:
            logging.info(f"Buscando documento: {document_type} {document_number}")
            
            # Navegar para a página de busca
            self.driver.get(self.base_url)
            time.sleep(3)
            
            if self.debug:
                logging.info(f"Página carregada: {self.driver.title}")
                # Salvar screenshot para debug
                self.driver.save_screenshot(f"debug_page_{document_number}.png")
            
            # Aguardar a página carregar completamente
            self.wait.until(EC.presence_of_element_located((By.ID, "numero")))
            
            # Limpar e preencher o campo de número do documento
            numero_input = self.driver.find_element(By.ID, "numero")
            numero_input.clear()
            
            # Remover decimais do número (ex: 501.0 -> 501)
            clean_number = str(int(float(document_number))) if '.' in str(document_number) else str(document_number)
            numero_input.send_keys(clean_number)
            
            logging.info(f"Campo preenchido com: {clean_number}")
            
            # Aguardar um pouco antes de clicar no botão
            time.sleep(2)
            
            # Procurar e clicar no botão de pesquisa com diferentes estratégias
            search_button = None
            button_selectors = [
                "button[title='Buscar conteúdo no site']",
                "button.btn-primary",
                "button[type='button']",
                "input[type='submit']",
                ".btn-primary"
            ]
            
            for selector in button_selectors:
                try:
                    search_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if search_button.is_displayed() and search_button.is_enabled():
                        break
                except NoSuchElementException:
                    continue
            
            if not search_button:
                logging.error("Botão de pesquisa não encontrado")
                return None
            
            # Tentar diferentes métodos de clique
            try:
                # Método 1: Clique normal
                search_button.click()
            except Exception as e1:
                try:
                    # Método 2: Clique via JavaScript
                    self.driver.execute_script("arguments[0].click();", search_button)
                except Exception as e2:
                    try:
                        # Método 3: Clique via ActionChains
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(self.driver).move_to_element(search_button).click().perform()
                    except Exception as e3:
                        logging.error(f"Falha ao clicar no botão: {e1}, {e2}, {e3}")
                        return None
            
            # Aguardar os resultados carregarem
            time.sleep(5)
            
            # Verificar se há resultados
            try:
                # Aguardar por mudança na página (resultados ou redirecionamento)
                self.wait.until(lambda driver: 
                    driver.current_url != self.base_url or 
                    len(driver.find_elements(By.CSS_SELECTOR, ".resultado-busca, .alert, .no-results, .result-item, .search-result, a[href*='exibenormativo']")) > 0
                )
                
                # Verificar se foi redirecionado para uma página de documento
                if "exibenormativo" in self.driver.current_url:
                    logging.info(f"Redirecionado diretamente para o documento: {self.driver.current_url}")
                    return True
                
                # Verificar se há mensagem de "nenhum resultado"
                no_results_selectors = [".alert", ".no-results", ".alert-warning", ".alert-info"]
                for selector in no_results_selectors:
                    no_results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if no_results and any("nenhum" in result.text.lower() or "não encontrado" in result.text.lower() for result in no_results):
                        logging.warning(f"Nenhum resultado encontrado para {document_type} {document_number}")
                        return None
                
                # Procurar por resultados com múltiplos seletores
                result_selectors = [
                    ".resultado-busca", ".result-item", ".search-result", 
                    "a[href*='exibenormativo']", ".normativo-item", ".documento-item",
                    ".list-group-item", ".card", ".row .col"
                ]
                
                results = []
                for selector in result_selectors:
                    results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if results:
                        break
                
                if not results:
                    # Se não encontrar resultados específicos, verificar se há links na página
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    results = [link for link in all_links if "exibenormativo" in link.get_attribute("href", "")]
                
                if not results:
                    logging.warning(f"Nenhum resultado encontrado para {document_type} {document_number}")
                    if self.debug:
                        # Salvar screenshot da página de resultados
                        self.driver.save_screenshot(f"debug_no_results_{document_number}.png")
                        logging.info(f"Screenshot salvo: debug_no_results_{document_number}.png")
                    
                    # Tentar abordagem alternativa: construir URL diretamente
                    logging.info("Tentando abordagem alternativa com URL direta...")
                    return self._try_direct_url(document_type, document_number)
                
                # Procurar pelo resultado que corresponde ao tipo e número
                target_result = None
                for result in results:
                    result_text = result.text.lower()
                    if (document_type.lower() in result_text and 
                        str(document_number) in result_text):
                        target_result = result
                        break
                
                if not target_result:
                    # Se não encontrar correspondência exata, usar o primeiro resultado
                    target_result = results[0]
                    logging.warning(f"Usando primeiro resultado disponível para {document_type} {document_number}")
                
                # Clicar no resultado
                if target_result.tag_name == 'a':
                    target_result.click()
                else:
                    # Se não for um link, procurar por um link dentro do elemento
                    link = target_result.find_element(By.CSS_SELECTOR, "a")
                    link.click()
                
                # Aguardar a página do documento carregar
                time.sleep(3)
                
                return True
                
            except TimeoutException:
                logging.error(f"Timeout aguardando resultados para {document_type} {document_number}")
                return None
                
        except Exception as e:
            logging.error(f"Erro ao buscar documento {document_type} {document_number}: {e}")
            return None

    def _try_direct_url(self, document_type, document_number):
        """Tenta acessar o documento usando URL direta"""
        try:
            # Construir URL baseada no padrão observado no CSV
            clean_number = str(int(float(document_number))) if '.' in str(document_number) else str(document_number)
            encoded_type = quote(document_type)
            direct_url = f"https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo={encoded_type}&numero={clean_number}"
            
            logging.info(f"Tentando URL direta: {direct_url}")
            
            # Navegar para a URL direta
            self.driver.get(direct_url)
            time.sleep(3)
            
            # Verificar se a página carregou corretamente
            if "exibenormativo" in self.driver.current_url:
                logging.info(f"Sucesso com URL direta: {self.driver.current_url}")
                return True
            else:
                logging.warning(f"URL direta não funcionou: {self.driver.current_url}")
                return None
                
        except Exception as e:
            logging.error(f"Erro ao tentar URL direta: {e}")
            return None

    def scrape_document_content(self, document_type, document_number, document_date):
        """Extrai o conteúdo do documento carregado"""
        try:
            # Aguardar o conteúdo do documento carregar
            time.sleep(2)
            
            # Tentar diferentes seletores para o conteúdo do documento
            content_selectors = [
                ".documento-conteudo",
                ".normativo-conteudo", 
                ".conteudo-documento",
                ".document-content",
                "#conteudo",
                ".main-content",
                "main",
                ".container .row"
            ]
            
            content_element = None
            for selector in content_selectors:
                try:
                    content_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if content_element and content_element.text.strip():
                        break
                except NoSuchElementException:
                    continue
            
            if not content_element:
                # Se não encontrar conteúdo específico, usar o body
                content_element = self.driver.find_element(By.TAG_NAME, "body")
            
            # Extrair texto
            content_text = content_element.text
            
            if not content_text.strip():
                logging.warning(f"Conteúdo vazio para {document_type} {document_number}")
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

    def process_documents(self, max_documents=None):
        """Processa todos os documentos do CSV"""
        try:
            # Ler o CSV
            df = pd.read_csv(self.csv_file)
            
            if max_documents:
                df = df.head(max_documents)
            
            total_docs = len(df)
            successful_docs = 0
            failed_docs = 0
            
            logging.info(f"Iniciando processamento de {total_docs} documentos")
            
            for index, row in df.iterrows():
                try:
                    document_type = row['tipo']
                    document_number = row['numero']
                    document_date = row['data']
                    
                    logging.info(f"Processando {index + 1}/{total_docs}: {document_type} {document_number}")
                    
                    # Buscar o documento
                    if self.search_document(document_number, document_type):
                        # Extrair conteúdo
                        result = self.scrape_document_content(document_type, document_number, document_date)
                        if result:
                            successful_docs += 1
                            logging.info(f"✓ Documento processado com sucesso: {document_type} {document_number}")
                        else:
                            failed_docs += 1
                            logging.error(f"✗ Falha ao extrair conteúdo: {document_type} {document_number}")
                    else:
                        failed_docs += 1
                        logging.error(f"✗ Falha ao buscar documento: {document_type} {document_number}")
                    
                    # Pausa entre requisições para evitar bloqueio
                    time.sleep(2)
                    
                except Exception as e:
                    failed_docs += 1
                    logging.error(f"Erro ao processar documento {index + 1}: {e}")
                    continue
            
            logging.info(f"Processamento concluído. Sucessos: {successful_docs}, Falhas: {failed_docs}")
            
        except Exception as e:
            logging.error(f"Erro no processamento geral: {e}")

    def close(self):
        """Fecha o driver"""
        if self.driver:
            self.driver.quit()
            logging.info("WebDriver fechado")

def main():
    """Função principal"""
    scraper = None
    try:
        # Criar instância do scraper em modo debug para teste
        scraper = BCBOfficialSearchScraper(debug=True)
        
        # Processar documentos (limitar a 2 para teste)
        scraper.process_documents(max_documents=2)
        
    except KeyboardInterrupt:
        logging.info("Processamento interrompido pelo usuário")
    except Exception as e:
        logging.error(f"Erro na execução: {e}")
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
