// Exporta las variantes TIFF de fixtures/tiff/ a partir de fixtures/_base_cmyk.tif.
// Requiere Photoshop. Ejecutar despues de generar_base.py, desde PowerShell:
//   $ps = New-Object -ComObject Photoshop.Application
//   $ps.DoJavaScriptFile("<ruta>\fixtures\exportar_tiffs.jsx")
// Deja el registro en fixtures/tiff/_export_log.txt.
#target photoshop
app.displayDialogs = DialogModes.NO;
app.preferences.rulerUnits = Units.PIXELS;
app.preferences.typeUnits = TypeUnits.PIXELS;

var DIR = File($.fileName).parent;
var SRC = File(DIR + "/_base_cmyk.tif");
var OUT = DIR + "/tiff/";
Folder(OUT).create();
var LOG = File(OUT + "_export_log.txt");
LOG.encoding = "UTF-8"; LOG.open("w");
function log(s){ LOG.writeln(s); }

function cmyk(c, m, y, k){
  var s = new SolidColor();
  s.cmyk.cyan = c; s.cmyk.magenta = m; s.cmyk.yellow = y; s.cmyk.black = k;
  return s;
}
function gris(g){ var s = new SolidColor(); s.gray.gray = g; return s; }
function rect(x0, y0, x1, y1){ return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]; }

function opts(comp, layers, alpha, spot, embed){
  var o = new TiffSaveOptions();
  o.imageCompression = comp;
  if (comp == TIFFEncoding.JPEG) o.jpegQuality = 10;
  o.layers = layers; o.alphaChannels = alpha; o.spotColor = spot;
  o.embedColorProfile = embed; o.byteOrder = ByteOrder.IBM;
  o.saveImagePyramid = false; o.annotations = false;
  if (!layers) o.transparency = false;
  return o;
}
function save(doc, name, o){
  try { doc.saveAs(File(OUT + name), o, true, Extension.LOWERCASE); log("OK    " + name); return true; }
  catch(e){ log("ERROR " + name + " -> " + e); return false; }
}
// Agrega un canal extra con un rectangulo relleno y deja activos los canales CMYK
function canalExtra(doc, tipo, nombre, color, zona){
  var comps = doc.componentChannels;
  var ch = doc.channels.add();
  ch.kind = tipo; ch.name = nombre;
  if (color) { ch.color = color; ch.opacity = 100; }
  doc.activeChannels = [ch];
  doc.selection.selectAll(); doc.selection.fill(gris(0));
  doc.selection.select(zona); doc.selection.fill(gris(100));
  doc.selection.deselect();
  doc.activeChannels = comps;
}

// --- Documento base con capas ---
var doc = app.open(SRC);
doc.colorProfileName = "Coated FOGRA39 (ISO 12647-2:2004)";

var txt = doc.artLayers.add();
txt.kind = LayerKind.TEXT;
txt.name = "Texto";
txt.textItem.contents = "muestras-rgb  prueba CMYK";
txt.textItem.size = 20; // puntos: a 300 dpi son ~83 px
txt.textItem.color = cmyk(0, 0, 0, 100);
txt.textItem.position = [80, 870];

var sup = doc.artLayers.add();
sup.name = "Superpuesta 60%";
doc.selection.select(rect(1250, 1150, 1950, 1600));
doc.selection.fill(cmyk(0, 100, 100, 0));
doc.selection.deselect();
sup.opacity = 60;

log(doc.width + "x" + doc.height + " " + doc.mode + " " + doc.bitsPerChannel +
    " perfil=" + doc.colorProfileName + " capas=" + doc.layers.length);

// 5. Con capas
save(doc, "08bit_capas_lzw.tif", opts(TIFFEncoding.TIFFLZW, true, false, false, true));

var flat = doc.duplicate("flat");
flat.flatten();
doc.close(SaveOptions.DONOTSAVECHANGES);

// 1-3, 7
save(flat, "08bit_lzw.tif",           opts(TIFFEncoding.TIFFLZW, false, false, false, true));
save(flat, "08bit_zip.tif",           opts(TIFFEncoding.TIFFZIP, false, false, false, true));
save(flat, "08bit_jpeg.tif",          opts(TIFFEncoding.JPEG,    false, false, false, true));
save(flat, "08bit_sinperfil_lzw.tif", opts(TIFFEncoding.TIFFLZW, false, false, false, false));

// 8. GRACoL
var g = flat.duplicate("gracol");
g.convertProfile("Coated GRACoL 2006 (ISO 12647-2:2004)", Intent.RELATIVECOLORIMETRIC, true, false);
save(g, "08bit_gracol2006_lzw.tif", opts(TIFFEncoding.TIFFLZW, false, false, false, true));
g.close(SaveOptions.DONOTSAVECHANGES);

// 4. 16 bits
var d16 = flat.duplicate("16bit");
d16.bitsPerChannel = BitsPerChannelType.SIXTEEN;
save(d16, "16bit_lzw.tif", opts(TIFFEncoding.TIFFLZW, false, false, false, true));
d16.close(SaveOptions.DONOTSAVECHANGES);

// 6a. Canal alfa guardado
var da = flat.duplicate("alfa");
canalExtra(da, ChannelType.MASKEDAREA, "Alfa 1", null, rect(400, 400, 1600, 1600));
save(da, "08bit_alfa_lzw.tif", opts(TIFFEncoding.TIFFLZW, false, true, false, true));
da.close(SaveOptions.DONOTSAVECHANGES);

// 6b. Tinta directa
var ds = flat.duplicate("tinta");
canalExtra(ds, ChannelType.SPOTCOLOR, "Tinta directa prueba", cmyk(0, 100, 0, 0), rect(200, 200, 800, 500));
save(ds, "08bit_tintadirecta_lzw.tif", opts(TIFFEncoding.TIFFLZW, false, false, true, true));
ds.close(SaveOptions.DONOTSAVECHANGES);

flat.close(SaveOptions.DONOTSAVECHANGES);
log("FIN");
LOG.close();
