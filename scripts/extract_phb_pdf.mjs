import { mkdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";

class DOMMatrix {
  constructor(init = [1, 0, 0, 1, 0, 0]) {
    const values = Array.from(init);
    [this.a, this.b, this.c, this.d, this.e, this.f] = [
      values[0] ?? 1,
      values[1] ?? 0,
      values[2] ?? 0,
      values[3] ?? 1,
      values[4] ?? 0,
      values[5] ?? 0,
    ];
  }

  multiply(other) {
    return new DOMMatrix([
      this.a * other.a + this.c * other.b,
      this.b * other.a + this.d * other.b,
      this.a * other.c + this.c * other.d,
      this.b * other.c + this.d * other.d,
      this.a * other.e + this.c * other.f + this.e,
      this.b * other.e + this.d * other.f + this.f,
    ]);
  }

  translate(x = 0, y = 0) {
    return this.multiply(new DOMMatrix([1, 0, 0, 1, x, y]));
  }

  scale(x = 1, y = x) {
    return this.multiply(new DOMMatrix([x, 0, 0, y, 0, 0]));
  }

  inverse() {
    const determinant = this.a * this.d - this.b * this.c;
    if (!determinant) {
      return new DOMMatrix();
    }
    return new DOMMatrix([
      this.d / determinant,
      -this.b / determinant,
      -this.c / determinant,
      this.a / determinant,
      (this.c * this.f - this.d * this.e) / determinant,
      (this.b * this.e - this.a * this.f) / determinant,
    ]);
  }
}

globalThis.DOMMatrix = DOMMatrix;
globalThis.ImageData = class ImageData {};
globalThis.Path2D = class Path2D {};

const [, , pdfPathArg, outputPathArg, pageRangeArg] = process.argv;
if (!pdfPathArg) {
  throw new Error(
    "Usage: node scripts/extract_phb_pdf.mjs <pdf-path> [output-json] [page-range]",
  );
}

const pdfJsPath =
  process.env.PDFJS_MODULE ??
  resolve(
    homedir(),
    ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/pdfjs-dist/legacy/build/pdf.mjs",
  );
const pdfjs = await import(pathToFileURL(pdfJsPath).href);
const bytes = await readFile(resolve(pdfPathArg));
const document = await pdfjs.getDocument({
  data: new Uint8Array(bytes),
  disableWorker: true,
}).promise;

function parsePageRange(value, pageCount) {
  if (!value) {
    return [1, pageCount];
  }
  const match = /^(\d+)(?:-(\d+))?$/.exec(value);
  if (!match) {
    throw new Error(`Invalid page range: ${value}`);
  }
  const start = Number(match[1]);
  const end = Number(match[2] ?? match[1]);
  if (start < 1 || end < start || end > pageCount) {
    throw new Error(`Page range must be within 1-${pageCount}: ${value}`);
  }
  return [start, end];
}

const [startPage, endPage] = parsePageRange(pageRangeArg, document.numPages);
const pages = [];
for (let pageNumber = startPage; pageNumber <= endPage; pageNumber += 1) {
  const page = await document.getPage(pageNumber);
  const content = await page.getTextContent();
  const text = content.items
    .map((item) => ("str" in item ? item.str : ""))
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  pages.push({ page: pageNumber, text });
}

const result = {
  source: resolve(pdfPathArg),
  page_count: document.numPages,
  extracted_range: [startPage, endPage],
  pages,
};
const serialized = `${JSON.stringify(result, null, 2)}\n`;

if (outputPathArg) {
  const outputPath = resolve(outputPathArg);
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, serialized, "utf8");
  console.log(
    `Extracted pages ${startPage}-${endPage} of ${document.numPages} to ${outputPath}`,
  );
} else {
  process.stdout.write(serialized);
}
