import sys
import requests
import json
import time
import io
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
from datetime import datetime, timedelta
from pypdf import PdfWriter, PdfReader
from rich.console import Console
from rich.progress import Progress, BarColumn, TaskProgressColumn, ProgressBar
from rich.text import Text

console = Console()


class SquareBarColumn(BarColumn):
    def render(self, task):
        """Render a bar with filled/empty circles."""
        complete = task.completed / task.total if task.total else 0
        width = self.bar_width
        filled = int(width * complete)
        
        
        bar = "●" * filled + "○" * (width - filled)
        style = "cyan" if complete < 1 else "green"
        return Text(f"[{bar}]", style=style)

BASE_URL  = "https://epaper.ntnews.com"
PAGES_API = BASE_URL + "/Home/GetAllpagespost"
PDF_GEN   = BASE_URL + "/Home/downloadpdfedition_page"
PDF_DL    = BASE_URL + "/Home/Download"


class EpaperDownloader:
    def __init__(self, output_dir=None):
        default = Path.home() / "Downloads" / "epaper_downloads"
        self.output_dir = Path(output_dir) if output_dir else default
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.5",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/Home/FullPage",
        })

        self.edition_id   = None
        self.edition_date = None
        self.pages_data   = []

    def parse_url(self, url):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        self.edition_id   = int(params.get("eid", [1])[0])
        self.edition_date = params.get("edate", [""])[0]

    def fetch_all_pages(self):
        payload = {"editionid": self.edition_id, "editiondate": self.edition_date, "email": ""}
        resp = self.session.post(PAGES_API, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            self.pages_data = data
        elif isinstance(data, dict) and "d" in data:
            inner = data["d"]
            self.pages_data = json.loads(inner) if isinstance(inner, str) else inner
        else:
            self.pages_data = []
        if not self.pages_data:
            console.print("[red]✗ API returned empty list[/red]")
            return False
        return True

    def get_edition_name(self):
        return self.pages_data[0].get("EditionName", "Edition") if self.pages_data else "Edition"

    def build_output_filename(self):
        edition_name = self.get_edition_name()
        name_part = edition_name.strip().replace(" ", "_")
        date_part = self.edition_date.replace("/", "-")
        return f"Namaste_Telangana_{name_part}_Paper_{date_part}.pdf"

    def build_monthly_filename(self, month_name):
        """Build filename for monthly merged PDF"""
        return f"Namaste_Telangana_{month_name}_Month_ALL_DATES.pdf"

    def download_newspaper(self, url):
        console.print("[bold cyan]NT NEWS EPAPER DOWNLOADER[/bold cyan]\n")
        self.parse_url(url)

        console.print(f"[white]Edition ID  :[/white] {self.edition_id}")
        console.print(f"[white]Edition Date:[/white] {self.edition_date}")

        with console.status("[bold green]Fetching page list..."):
            if not self.fetch_all_pages():
                return False
            edition_name = self.get_edition_name()
            console.print(f"[white]Edition Name:[/white] {edition_name}")
            console.print(f"[white]Total Pages :[/white] {len(self.pages_data)}\n")

        out_filename = self.build_output_filename()
        out_path     = self.output_dir / out_filename
        writer       = PdfWriter()
        total        = len(self.pages_data)
        success      = 0
        failed       = []

        with Progress(
            "[progress.description]{task.description}",
            SquareBarColumn(bar_width=40),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Downloading pages...", total=total)

            for page in self.pages_data:
                page_no = page.get("PageNo") or page.get("PageNumber", "?")
                try:
                    idx = int(str(page_no).strip())
                except (ValueError, TypeError):
                    idx = success + 1

                page_id = page.get("PageId") or page.get("pageId")
                if not page_id:
                    failed.append(f"Page {page_no}: missing PageId")
                    progress.update(task, advance=1)
                    continue

                try:
                    gen_resp = self.session.get(
                        PDF_GEN,
                        params={"id": page_id, "type": 1, "EditionId": self.edition_id, "Date": self.edition_date},
                        timeout=120,
                    )
                    gen_resp.raise_for_status()
                    filename = gen_resp.json().get("FileName")
                    if not filename:
                        failed.append(f"Page {idx}: no FileName")
                        progress.update(task, advance=1)
                        continue

                    dl_resp = self.session.get(f"{PDF_DL}?Filename={quote(filename)}", timeout=60)
                    dl_resp.raise_for_status()

                    reader = PdfReader(io.BytesIO(dl_resp.content))
                    for p in reader.pages:
                        writer.add_page(p)

                    success += 1
                    time.sleep(0.1)

                except Exception as e:
                    failed.append(f"Page {idx}: {str(e)}")

                progress.update(task, advance=1)

        console.print()

        if success == 0:
            console.print("[red]✗ No pages downloaded[/red]")
            return False

        with open(out_path, "wb") as f:
            writer.write(f)

        size_mb = out_path.stat().st_size / (1024 * 1024)
        console.print(f"[green]✓ PDF saved[/green]  {out_path.name}")
        console.print(f"[white]  Pages    :[/white] {success}/{total}")
        console.print(f"[white]  Size     :[/white] {size_mb:.2f} MB\n")

        if failed:
            console.print(f"[yellow]⚠ {len(failed)} page(s) skipped[/yellow]")

        return True

    def download_date_pages(self, edition_id, date_str, edition_name=None):
        """Download all pages for a specific date and return PdfWriter with merged pages"""
        self.edition_id = edition_id
        self.edition_date = date_str
        self.pages_data = []
        
        payload = {"editionid": edition_id, "editiondate": date_str, "email": ""}
        try:
            resp = self.session.post(PAGES_API, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                self.pages_data = data
            elif isinstance(data, dict) and "d" in data:
                inner = data["d"]
                self.pages_data = json.loads(inner) if isinstance(inner, str) else inner
            else:
                self.pages_data = []
            
            if not self.pages_data:
                return None
                
        except Exception as e:
            console.print(f"  [red]✗ Failed to fetch pages for {date_str}: {str(e)}[/red]")
            return None

        writer = PdfWriter()
        total = len(self.pages_data)
        success = 0

        for page in self.pages_data:
            try:
                page_id = page.get("PageId") or page.get("pageId")
                if not page_id:
                    continue

                gen_resp = self.session.get(
                    PDF_GEN,
                    params={"id": page_id, "type": 1, "EditionId": edition_id, "Date": date_str},
                    timeout=120,
                )
                gen_resp.raise_for_status()
                filename = gen_resp.json().get("FileName")
                if not filename:
                    continue

                dl_resp = self.session.get(f"{PDF_DL}?Filename={quote(filename)}", timeout=60)
                dl_resp.raise_for_status()

                reader = PdfReader(io.BytesIO(dl_resp.content))
                for p in reader.pages:
                    writer.add_page(p)

                success += 1
                time.sleep(0.05)

            except Exception:
                continue

        return writer if success > 0 else None

    def download_date_range(self, start_date, end_date, edition_id=1):
        """Download newspapers for a date range, saving each date as separate PDF"""
        console.print("[bold cyan]NT NEWS EPAPER - BATCH DOWNLOAD[/bold cyan]\n")
        
        # Parse dates
        start = datetime.strptime(start_date, "%d/%m/%Y")
        end = datetime.strptime(end_date, "%d/%m/%Y")
        
        console.print(f"[white]Date Range  :[/white] {start_date} to {end_date}")
        console.print(f"[white]Edition ID  :[/white] {edition_id}\n")
        
        # Collect all dates
        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%d/%m/%Y"))
            current += timedelta(days=1)
        
        # Month name mapping
        month_names_map = {
            "01": "January", "02": "February", "03": "March", "04": "April",
            "05": "May", "06": "June", "07": "July", "08": "August",
            "09": "September", "10": "October", "11": "November", "12": "December"
        }
        
        successful = 0
        failed = 0

        with Progress(
            "[progress.description]{task.description}",
            SquareBarColumn(bar_width=40),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Downloading {len(dates)} dates...", total=len(dates))

            for date_str in dates:
                page_writer = self.download_date_pages(edition_id, date_str)
                
                if page_writer:
                    # Get month name from date
                    date_obj = datetime.strptime(date_str, "%d/%m/%Y")
                    month_name = month_names_map[date_obj.strftime("%m")]
                    day = date_obj.strftime("%d")
                    
                    # Create filename: Namaste_Telangana_Jan_01_01_2026.pdf
                    out_filename = f"Namaste_Telangana_{month_name}_{day}_{date_str.replace('/', '_')}.pdf"
                    out_path = self.output_dir / out_filename
                    
                    # Save PDF
                    with open(out_path, "wb") as f:
                        page_writer.write(f)
                    
                    size_mb = out_path.stat().st_size / (1024 * 1024)
                    console.print(f"  [green]✓[/green] {date_str}: {out_filename} ({size_mb:.2f} MB, {len(page_writer.pages)} pages)")
                    successful += 1
                    
                    time.sleep(0.5)
                else:
                    failed += 1
                
                progress.update(task, advance=1)

        console.print()
        console.print(f"[green]✓ Download complete[/green]")
        console.print(f"[white]  Successful :[/white] {successful}/{len(dates)}")
        console.print(f"[white]  Failed     :[/white] {failed}/{len(dates)}\n")

        return successful > 0


def main():
    if len(sys.argv) < 2:
        console.print("[white]Usage:[/white]")
        console.print("  Single edition: python Epaper.py <URL> [output_dir]")
        console.print("  Batch download: python Epaper.py --batch <start_date> <end_date> [edition_id] [output_dir]")
        console.print()
        console.print("[white]Examples:[/white]")
        console.print('  python Epaper.py "https://epaper.ntnews.com/HyderabadMain?eid=1&edate=09/03/2026"')
        console.print('  python Epaper.py --batch "01/01/2026" "09/03/2026" 1')
        return

    if sys.argv[1] == "--batch":
        if len(sys.argv) < 4:
            console.print("[red]✗ Batch mode requires: --batch <start_date> <end_date> [edition_id] [output_dir][/red]")
            return
        
        start_date = sys.argv[2]
        end_date = sys.argv[3]
        edition_id = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        output_dir = sys.argv[5] if len(sys.argv) > 5 else None
        
        dl = EpaperDownloader(output_dir)
        if not dl.download_date_range(start_date, end_date, edition_id):
            console.print("[red]✗ Batch download failed[/red]")
            sys.exit(1)
        console.print("[green]Done![/green]")
    else:
        url = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else None

        dl = EpaperDownloader(output_dir)
        if not dl.download_newspaper(url):
            console.print("[red]✗ Download failed[/red]")
            sys.exit(1)
        console.print("[green]Done![/green]")


if __name__ == "__main__":
    main()
