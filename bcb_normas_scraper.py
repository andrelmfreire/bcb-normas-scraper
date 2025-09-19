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
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Configuracao de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bcb_scraper.log'),
        logging.StreamHandler()
    ]
)

class BCBNormativesScraperFinal:
    def __init__(self, csv_file='normativos_spb_bcb.csv', output_dir='normativos_txt'):
        self.csv_file = csv_file
        self.output_dir = output_dir
        self.driver = None
        self.wait = None

        # Criar diretorio de saída
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Configurar Selenium WebDriver
        self._setup_driver()

    def _setup_driver(self, headless=True):
        """Configura o WebDriver do Selenium"""
        try:
            # Configurações do Chrome para evitar detecção de bot
            chrome_options = Options()
            
            # Modo headless (configurável)
            if headless:
                chrome_options.add_argument('--headless=new')  # Usar nova versão do headless
            
            # Configurações básicas
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # User agent mais recente e realista
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Configurações para evitar detecção de bot
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Configurações adicionais para stealth
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-hang-monitor')
            chrome_options.add_argument('--disable-prompt-on-repost')
            chrome_options.add_argument('--disable-domain-reliability')
            chrome_options.add_argument('--disable-component-extensions-with-background-pages')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-breakpad')
            chrome_options.add_argument('--disable-component-update')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            
            # Configurações de rede e performance
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # Desabilitar imagens para acelerar
            
            # Configurações de idioma e localização
            chrome_options.add_argument('--lang=pt-BR')
            chrome_options.add_argument('--accept-lang=pt-BR,pt;q=0.9,en;q=0.8')
            
            # Configurações de memória e performance
            chrome_options.add_argument('--memory-pressure-off')
            chrome_options.add_argument('--max_old_space_size=4096')
            
            # Desabilitar notificações e popups
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 2,
                    "geolocation": 2,
                    "media_stream": 2,
                },
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.media_stream": 2,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Instalar e configurar o ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Executar scripts para ocultar propriedades de automação
            stealth_scripts = [
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
                "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})",
                "Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']})",
                "Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})})",
                "window.chrome = {runtime: {}}",
                "Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'})",
                "Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8})",
                "Object.defineProperty(navigator, 'deviceMemory', {get: () => 8})",
            ]
            
            for script in stealth_scripts:
                try:
                    self.driver.execute_script(script)
                except:
                    pass
            
            # Configurar timeouts
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 30)
            
            logging.info(f"WebDriver configurado com sucesso (headless={headless})")
            
        except Exception as e:
            logging.error(f"Erro ao configurar WebDriver: {e}")
            raise

    def close_driver(self):
        """Fecha o WebDriver"""
        if self.driver:
            self.driver.quit()
            logging.info("WebDriver fechado")

    def load_documents(self):
        """Carrega a lista de documentos do CSV"""
        try:
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            logging.info(f"Carregados {len(df)} documentos do CSV")
            return df
        except Exception as e:
            logging.error(f"Erro ao carregar CSV: {e}")
            return None

    def get_url_from_csv(self, row):
        """Obtém a URL correta do CSV"""
        if 'url_bcb' in row and pd.notna(row['url_bcb']):
            return row['url_bcb']
        else:
            # Fallback: construir URL se não estiver no CSV
            tipo_encoded = quote(row['tipo'])
            numero_encoded = quote(str(row['numero']))
            return f"https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo={tipo_encoded}&numero={numero_encoded}"

    def try_direct_pdf_access(self, tipo, numero):
        """Tenta acessar o PDF diretamente"""
        try:
            # Codificar tipo e numero
            tipo_encoded = quote(tipo)
            numero_encoded = quote(str(numero))
            
            # Padrões de URL para PDFs
            pdf_patterns = [
                f"https://www.bcb.gov.br/estabilidadefinanceira/normativo/pdf/{tipo_encoded}_{numero_encoded}.pdf",
                f"https://www.bcb.gov.br/estabilidadefinanceira/normativo/pdf/{tipo_encoded}_{numero_encoded}.0.pdf",
                f"https://www.bcb.gov.br/estabilidadefinanceira/normativo/{tipo_encoded}_{numero_encoded}.pdf",
                f"https://www.bcb.gov.br/estabilidadefinanceira/normativo/{tipo_encoded}_{numero_encoded}.0.pdf",
            ]
            
            for pdf_url in pdf_patterns:
                try:
                    response = requests.get(pdf_url, timeout=10)
                    if response.status_code == 200 and 'application/pdf' in response.headers.get('content-type', ''):
                        logging.info(f"PDF encontrado: {pdf_url}")
                        return pdf_url
                except:
                    continue
                    
        except Exception as e:
            logging.warning(f"Erro ao tentar acessar PDF: {e}")
        
        return None

    def extract_content_with_multiple_strategies(self, row):
        """Tenta múltiplas estratégias para extrair o conteúdo"""
        tipo = row['tipo']
        numero = row['numero']
        
        # Estratégia 1: Tentar acessar PDF diretamente
        pdf_url = self.try_direct_pdf_access(tipo, numero)
        if pdf_url:
            return f"[PDF encontrado: {pdf_url}]"
        
        # Estratégia 2: Tentar com headless primeiro
        content = self._try_extract_with_driver(row, headless=True)
        if content:
            return content
        
        # Estratégia 3: Tentar sem headless se headless falhou
        logging.info("Tentando sem headless mode...")
        try:
            self.close_driver()
            self._setup_driver(headless=False)
            content = self._try_extract_with_driver(row, headless=False)
            if content:
                return content
        except Exception as e:
            logging.error(f"Erro ao tentar sem headless: {e}")
        
        logging.error("Todas as estratégias falharam")
        return None

    def _try_extract_with_driver(self, row, headless=True):
        """Tenta extrair conteúdo com configuração específica do driver"""
        url = self.get_url_from_csv(row)
        
        try:
            logging.info(f"Usando URL do CSV: {url} (headless={headless})")
            
            # Navegar para a página
            self.driver.get(url)
            
            # Aguardar carregamento inicial
            time.sleep(8)
            
            # Verificar se há mensagem de JavaScript
            page_text = self.driver.page_source
            if "Essa pagina depende do javascript" in page_text or "habilitar o javascript" in page_text:
                logging.warning("URL ainda mostra mensagem de JavaScript")
                return None
            
            # Tentar aguardar por elementos específicos que indicam que o conteúdo foi carregado
            try:
                # Aguardar por elementos que indicam carregamento do conteúdo
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.by import By
                
                # Aguardar até 30 segundos por elementos que indicam conteúdo carregado
                wait = WebDriverWait(self.driver, 30)
                
                # Tentar aguardar por elementos que indicam que o documento foi carregado
                try:
                    # Aguardar por elementos que contêm texto de documento
                    wait.until(lambda driver: any([
                        'Art.' in driver.page_source,
                        'Parágrafo' in driver.page_source,
                        'Considerando' in driver.page_source,
                        'RESOLUÇÃO' in driver.page_source.upper(),
                        'INSTRUÇÃO' in driver.page_source.upper()
                    ]))
                    logging.info("Elementos de documento detectados na página")
                except:
                    logging.warning("Timeout aguardando elementos de documento")
                
            except Exception as e:
                logging.warning(f"Erro ao aguardar elementos: {e}")
            
            # Aguardar carregamento dinâmico com estratégias mais robustas
            max_wait_attempts = 25
            content_found = False
            
            for wait_attempt in range(max_wait_attempts):
                time.sleep(2)
                
                try:
                    # Verificar se o conteúdo foi carregado usando JavaScript
                    content_indicators = self.driver.execute_script("""
                        var text = document.body.innerText || document.body.textContent || '';
                        var indicators = ['RESOLUÇÃO', 'BANCO CENTRAL', 'Art.', 'Parágrafo', 'Considerando', 'Visto', 'Brasília', 'INSTRUÇÃO', 'CIRCULAR'];
                        var found = indicators.filter(ind => text.toUpperCase().includes(ind));
                        return {
                            found: found,
                            hasContent: text.length > 2000,
                            textLength: text.length,
                            hasNavigation: text.includes('ACESSIBILIDADE') && text.includes('ALTO CONTRASTE'),
                            hasDocumentContent: text.includes('Art.') || text.includes('Parágrafo') || text.includes('Considerando'),
                            hasNoscript: document.querySelector('noscript') !== null
                        };
                    """)
                    
                    logging.info(f"  Aguardando {wait_attempt + 1}: Indicadores: {content_indicators['found']}, Tamanho: {content_indicators['textLength']}, Navegação: {content_indicators['hasNavigation']}, Documento: {content_indicators['hasDocumentContent']}, NoScript: {content_indicators['hasNoscript']}")
                    
                    # Se encontrou indicadores de documento e não é só navegação
                    if (len(content_indicators['found']) >= 2 and 
                        content_indicators['hasContent'] and 
                        not content_indicators['hasNavigation'] and
                        content_indicators['hasDocumentContent']):
                        logging.info("Conteúdo do documento encontrado!")
                        content_found = True
                        break
                        
                except Exception as e:
                    logging.warning(f"Erro ao verificar conteúdo na tentativa {wait_attempt + 1}: {e}")
                    continue
            
            if not content_found:
                logging.warning("Conteúdo não foi carregado após todas as tentativas")
                return None
            
            # Procurar por elementos que contêm o conteúdo do documento
            content_element = self.find_document_content()
            
            if content_element:
                text = content_element.text
                
                # Verificar se contém indicadores de documento
                text_upper = text.upper()
                indicators = ['RESOLUÇÃO', 'BANCO CENTRAL', 'Art.', 'Parágrafo', 'Considerando', 'Visto', 'Brasília', 'INSTRUÇÃO', 'CIRCULAR']
                found_indicators = [ind for ind in indicators if ind in text_upper]
                
                # Verificar se não é apenas navegação
                nav_indicators = ['ACESSIBILIDADE', 'ALTO CONTRASTE', 'ENGLISH', 'Home', 'Estabilidade', 'financeira']
                nav_found = [ind for ind in nav_indicators if ind in text_upper]
                
                if len(found_indicators) >= 2 and len(nav_found) < 3:
                    logging.info(f"Conteúdo válido encontrado com {len(found_indicators)} indicadores")
                    return self.clean_text(text)
                else:
                    logging.warning(f"Conteúdo inválido: {len(found_indicators)} indicadores de documento, {len(nav_found)} indicadores de navegação")
                    # Mesmo assim, tentar retornar o conteúdo se for longo o suficiente
                    if len(text) > 1000:
                        logging.info("Retornando conteúdo mesmo com poucos indicadores (texto longo)")
                        return self.clean_text(text)
            
        except Exception as e:
            logging.error(f"Erro ao extrair conteúdo: {e}")
        
        return None

    def find_document_content(self):
        """Encontra o elemento que contém o conteúdo do documento"""
        try:
            # Procurar por elementos que contêm o conteúdo do documento
            content_selectors = [
                'div[class*="conteudo"]',
                'div[class*="documento"]',
                'div[class*="normativo"]',
                'div[class*="texto"]',
                'div[class*="body"]',
                'div[class*="main"]',
                'div[class*="content"]',
                'article',
                'main',
                'div[class*="normativo-conteudo"]',
                'div[class*="documento-conteudo"]'
            ]
            
            for selector in content_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.text and len(element.text) > 1000:
                            text_upper = element.text.upper()
                            if any(word in text_upper for word in ['RESOLUÇÃO', 'BANCO CENTRAL', 'Art.', 'Parágrafo', 'Considerando']):
                                logging.info(f"Conteúdo encontrado com seletor: {selector}")
                                return element
                except:
                    continue
            
            # Estratégia alternativa: procurar por todos os elementos
            all_elements = self.driver.find_elements(By.XPATH, "//*")
            best_element = None
            best_score = 0
            
            for element in all_elements:
                if element.text and len(element.text) > 2000:
                    text_upper = element.text.upper()
                    score = 0
                    
                    # Pontuar baseado em indicadores de documento
                    indicators = ['RESOLUÇÃO', 'BANCO CENTRAL', 'Art.', 'Parágrafo', 'Considerando', 'Visto', 'Brasília']
                    for indicator in indicators:
                        if indicator in text_upper:
                            score += 1
                    
                    # Penalizar se contém muito texto de navegação
                    nav_indicators = ['ACESSIBILIDADE', 'ALTO CONTRASTE', 'ENGLISH', 'Home', 'Estabilidade', 'financeira']
                    for nav_indicator in nav_indicators:
                        if nav_indicator in text_upper:
                            score -= 0.5
                    
                    if score > best_score:
                        best_score = score
                        best_element = element
            
            if best_element and best_score > 0:
                logging.info(f"Melhor elemento encontrado com score: {best_score}")
                return best_element
                
        except Exception as e:
            logging.error(f"Erro ao encontrar conteúdo: {e}")
        
        return None

    def clean_text(self, text):
        """Limpa o texto extraído"""
        # Limpeza do texto
        text = re.sub(r'\n+', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        return text.strip()

    def scrape_document(self, row):
        """Faz scraping de um documento específico"""
        tipo = row['tipo']
        numero = row['numero']
        assunto = row['assunto']
        
        filename = self.generate_filename(tipo, numero, assunto)
        filepath = os.path.join(self.output_dir, filename)

        # Verificar se arquivo já existe
        if os.path.exists(filepath):
            logging.info(f"Arquivo já existe, pulando: {filename}")
            return True

        try:
            logging.info(f"Fazendo scraping: {tipo} nro. {numero}")

            # Usar múltiplas estratégias para extrair conteúdo
            content = self.extract_content_with_multiple_strategies(row)

            if not content:
                logging.error(f"Conteúdo vazio para {tipo} nro. {numero}")
                return False

            # Verificar se o conteúdo é válido
            if len(content) < 500:
                logging.error(f"Conteúdo muito curto para {tipo} nro. {numero} ({len(content)} caracteres)")
                return False

            # Criar cabeçalho do arquivo
            header = f"""# {tipo} nro. {numero}
# Data de acesso: {time.strftime('%d/%m/%Y %H:%M:%S')}
# Assunto: {assunto}
# ========================================

"""

            # Salvar arquivo
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(header + content)

            logging.info(f"Salvo com sucesso: {filename}")
            return True

        except Exception as e:
            logging.error(f"Erro inesperado para {tipo} nro. {numero}: {e}")
            return False

    def generate_filename(self, tipo, numero, assunto):
        """Gera nome de arquivo seguro"""
        # Limpar tipo e numero
        tipo_clean = re.sub(r'[^A-Za-z0-9]', '_', tipo)
        # Converter numero para string e remover .0 se existir
        numero_str = str(numero)
        if numero_str.endswith('.0'):
            numero_str = numero_str[:-2]
        numero_clean = re.sub(r'[^A-Za-z0-9._-]', '_', numero_str)

        # Criar nome base
        base_name = f"{tipo_clean}_n{numero_clean}"

        # Adicionar parte do assunto (primeiras palavras, limitado)
        assunto_clean = re.sub(r'[^A-Za-z0-9 ]', '', assunto)
        assunto_words = assunto_clean.split()[:5]  # Primeiras 5 palavras
        assunto_part = '_'.join(assunto_words).lower()

        if assunto_part:
            filename = f"{base_name}_{assunto_part}.txt"
        else:
            filename = f"{base_name}.txt"

        # Limitar tamanho do nome do arquivo
        if len(filename) > 200:
            filename = filename[:197] + "...txt"

        return filename

    def run_scraper(self, delay=3):
        """Executa o scraping de todos os documentos"""
        df = self.load_documents()
        if df is None:
            return

        successful = 0
        failed = 0

        try:
            for index, row in df.iterrows():
                try:
                    if self.scrape_document(row):
                        successful += 1
                    else:
                        failed += 1

                    # Delay entre requisições para não sobrecarregar o servidor
                    if delay > 0 and index < len(df) - 1:  # Não esperar no último
                        time.sleep(delay)

                except KeyboardInterrupt:
                    logging.info("Scraping interrompido pelo usuário")
                    break
                except Exception as e:
                    logging.error(f"Erro inesperado na linha {index}: {e}")
                    failed += 1

        finally:
            # Sempre fechar o driver
            self.close_driver()

        logging.info(f"Scraping concluído. Sucessos: {successful}, Falhas: {failed}")

        # Relatório final
        print(f"\n=== RELATÓRIO FINAL ===")
        print(f"Documentos processados com sucesso: {successful}")
        print(f"Documentos com falha: {failed}")
        print(f"Arquivos salvos em: {self.output_dir}")

        # Listar arquivos criados
        txt_files = list(Path(self.output_dir).glob("*.txt"))
        print(f"\nTotal de arquivos .txt criados: {len(txt_files)}")

        if txt_files:
            print("\nPrimeiros arquivos criados:")
            for i, file in enumerate(txt_files[:5]):
                print(f"  - {file.name}")
            if len(txt_files) > 5:
                print(f"  ... e mais {len(txt_files) - 5} arquivos")

# Função principal para executar o scraper
def main():
    print("=== BCB Normativos Scraper (Final) ===")
    print("Este script irá fazer download de todos os normativos do SPB")
    print("usando múltiplas estratégias para contornar problemas de JavaScript")

    # Verificar se o CSV existe
    csv_file = 'normativos_spb_bcb.csv'
    if not os.path.exists(csv_file):
        print(f"ERRO: Arquivo {csv_file} não encontrado!")
        print("Execute primeiro o script de busca dos documentos.")
        return

    # Configurar delay entre requisições
    delay = input("\nDelay entre requisições (segundos) [default: 3]: ").strip()
    try:
        delay = float(delay) if delay else 3.0
    except ValueError:
        delay = 3.0

    print(f"\nIniciando scraping com delay de {delay} segundos...")

    # Executar scraper
    scraper = BCBNormativesScraperFinal()
    try:
        scraper.run_scraper(delay=delay)
    except Exception as e:
        print(f"Erro durante a execução: {e}")
        scraper.close_driver()

if __name__ == "__main__":
    main()
