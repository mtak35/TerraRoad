# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Local, offline interface catalogs. Never change stored style/parameter keys.

Long original author notes and uncommon technical options fall back to English.
Languages cover ten widely spoken languages plus Urdu. Technical wording can be
refined by editing these catalogs; no network or translation service is used.
"""
import re

LANGUAGES=[('en','English'),('zh','中文（普通话）'),('hi','हिन्दी'),('es','Español'),
           ('fr','Français'),('ar','العربية'),('bn','বাংলা'),('pt','Português'),
           ('ru','Русский'),('id','Bahasa Indonesia'),('ur','اردو')]
ORDER=['zh','hi','es','fr','ar','bn','pt','ru','id','ur']

# Each row: English | Chinese | Hindi | Spanish | French | Arabic | Bengali |
# Portuguese | Russian | Indonesian | Urdu.
ROWS='''
Language|语言|भाषा|Idioma|Langue|اللغة|ভাষা|Idioma|Язык|Bahasa|زبان
Measurement system|计量单位制|मापन प्रणाली|Sistema de unidades|Système d’unités|نظام القياس|পরিমাপ পদ্ধতি|Sistema de unidades|Система единиц|Sistem satuan|پیمائش کا نظام
Metric (m, m², m³)|公制 (m, m², m³)|मीट्रिक (m, m², m³)|Métrico (m, m², m³)|Métrique (m, m², m³)|متري (m, m², m³)|মেট্রিক (m, m², m³)|Métrico (m, m², m³)|Метрическая (м, м², м³)|Metrik (m, m², m³)|میٹرک (m, m², m³)
Imperial (ft/in, ft², ft³)|英制 (ft/in, ft², ft³)|इंपीरियल (ft/in, ft², ft³)|Imperial (ft/in, ft², ft³)|Impérial (ft/in, ft², ft³)|إمبراطوري (ft/in, ft², ft³)|ইম্পেরিয়াল (ft/in, ft², ft³)|Imperial (ft/in, ft², ft³)|Имперская (ft/in, ft², ft³)|Imperial (ft/in, ft², ft³)|امپیریل (ft/in, ft², ft³)
Edit a road|编辑道路|सड़क संपादित करें|Editar una vía|Modifier une route|تعديل طريق|রাস্তা সম্পাদনা|Editar uma via|Редактирование дороги|Edit jalan|سڑک میں ترمیم
Convert face into road|将面转换为道路|फलक को सड़क बनाएँ|Convertir cara en vía|Convertir une face en route|تحويل سطح إلى طريق|পৃষ্ঠকে রাস্তায় রূপান্তর|Converter face em via|Преобразовать грань в дорогу|Ubah bidang menjadi jalan|سطح کو سڑک بنائیں
Alignment|路线|संरेखण|Alineación|Tracé|المحاذاة|অ্যালাইনমেন্ট|Alinhamento|Трасса|Alinyemen|الائنمنٹ
Junctions & roundabouts|交叉口与环岛|चौराहे और गोल चक्कर|Intersecciones y glorietas|Carrefours et giratoires|التقاطعات والدوارات|মোড় ও গোলচত্বর|Interseções e rotatórias|Перекрёстки и кольцевые развязки|Simpang dan bundaran|چوراہے اور گول چکر
Site & map|场地与地图|स्थल और मानचित्र|Sitio y mapa|Site et carte|الموقع والخريطة|স্থান ও মানচিত্র|Local e mapa|Участок и карта|Lokasi dan peta|مقام اور نقشہ
Roadway|车行道|सड़क मार्ग|Calzada|Chaussée|مسار الطريق|সড়কপথ|Pista|Проезжая часть|Badan jalan|سڑک کی تفصیل
Junctions|交叉口|चौराहे|Intersecciones|Carrefours|التقاطعات|মোড়|Interseções|Перекрёстки|Persimpangan|چوراہے
Central median|中央分隔带|केंद्रीय विभाजक|Mediana central|Terre-plein central|الجزيرة الوسطية|কেন্দ্রীয় বিভাজক|Canteiro central|Разделительная полоса|Median tengah|درمیانی پٹی
Shoulder|路肩|सड़क का कंधा|Arcén|Accotement|كتف الطريق|রাস্তার কাঁধ|Acostamento|Обочина|Bahu jalan|شولڈر
Service road|辅路|सर्विस रोड|Vía de servicio|Voie de desserte|طريق الخدمة|সার্ভিস রোড|Via de serviço|Боковой проезд|Jalan layanan|سروس روڈ
Parking bay|停车带|पार्किंग क्षेत्र|Zona de estacionamiento|Bande de stationnement|موقف سيارات|পার্কিং স্থান|Faixa de estacionamento|Парковочная полоса|Petak parkir|پارکنگ کی جگہ
Curb|路缘石|कर्ब|Bordillo|Bordure|حجر الرصيف|কার্ব|Meio-fio|Бордюр|Kerb|کرب
Sidewalk and planting|人行道与绿化|फुटपाथ और रोपण|Acera y vegetación|Trottoir et plantations|الرصيف والتشجير|ফুটপাত ও রোপণ|Calçada e vegetação|Тротуар и озеленение|Trotoar dan tanaman|فٹ پاتھ اور شجرکاری
Lane markings|车道标线|लेन चिह्न|Marcas viales|Marquage des voies|علامات الحارات|লেন চিহ্ন|Sinalização de faixas|Дорожная разметка|Marka lajur|لین کی نشانیاں
High tension line|高压线路|उच्च वोल्टेज लाइन|Línea de alta tensión|Ligne haute tension|خط جهد عالٍ|উচ্চ ভোল্টেজ লাইন|Linha de alta tensão|Линия электропередачи|Saluran tegangan tinggi|ہائی ٹینشن لائن
Light poles|路灯杆|प्रकाश स्तंभ|Postes de alumbrado|Candélabres|أعمدة الإنارة|বাতির খুঁটি|Postes de iluminação|Опоры освещения|Tiang lampu|بجلی کے کھمبے
Zebra crossings|斑马线|ज़ेब्रा क्रॉसिंग|Pasos de peatones|Passages piétons|معابر المشاة|জেব্রা ক্রসিং|Faixas de pedestres|Пешеходные переходы|Penyeberangan zebra|زیبرا کراسنگ
Traffic signals|交通信号灯|यातायात संकेत|Semáforos|Feux de circulation|إشارات المرور|ট্রাফিক সংকেত|Semáforos|Светофоры|Lampu lalu lintas|ٹریفک سگنل
Grading to terrain|地形放坡|भूभाग से ढलान मिलान|Taludes al terreno|Raccordement au terrain|تسوية مع التضاريس|ভূখণ্ডে ঢাল মেলানো|Taludes ao terreno|Сопряжение с рельефом|Perataan ke medan|زمین کے مطابق ڈھلوان
Materials|材质|सामग्री|Materiales|Matériaux|المواد|উপকরণ|Materiais|Материалы|Material|مواد
Create|创建|बनाएँ|Crear|Créer|إنشاء|তৈরি করুন|Criar|Создать|Buat|بنائیں
Update selected road|更新所选道路|चयनित सड़क अद्यतन करें|Actualizar vía seleccionada|Actualiser la route sélectionnée|تحديث الطريق المحدد|নির্বাচিত রাস্তা হালনাগাদ|Atualizar via selecionada|Обновить выбранную дорогу|Perbarui jalan terpilih|منتخب سڑک اپ ڈیٹ کریں
Convert to a road|转换为道路|सड़क में बदलें|Convertir en vía|Convertir en route|تحويل إلى طريق|রাস্তায় রূপান্তর|Converter em via|Преобразовать в дорогу|Ubah menjadi jalan|سڑک میں تبدیل کریں
Convert to a junction|转换为交叉口|चौराहे में बदलें|Convertir en intersección|Convertir en carrefour|تحويل إلى تقاطع|মোড়ে রূপান্তর|Converter em interseção|Преобразовать в перекрёсток|Ubah menjadi simpang|چوراہے میں تبدیل کریں
Apply|应用|लागू करें|Aplicar|Appliquer|تطبيق|প্রয়োগ করুন|Aplicar|Применить|Terapkan|لاگو کریں
Save as…|另存为…|इस रूप में सहेजें…|Guardar como…|Enregistrer sous…|حفظ باسم…|নতুন নামে সংরক্ষণ…|Salvar como…|Сохранить как…|Simpan sebagai…|نئے نام سے محفوظ کریں…
Delete|删除|हटाएँ|Eliminar|Supprimer|حذف|মুছুন|Excluir|Удалить|Hapus|حذف کریں
Close|关闭|बंद करें|Cerrar|Fermer|إغلاق|বন্ধ করুন|Fechar|Закрыть|Tutup|بند کریں
Reset defaults|恢复默认值|डिफ़ॉल्ट बहाल करें|Restablecer valores|Valeurs par défaut|استعادة الافتراضي|ডিফল্ট পুনরুদ্ধার|Restaurar padrões|Сбросить настройки|Atur ulang bawaan|اصل ترتیبات بحال کریں
Load design settings|加载设计设置|डिज़ाइन सेटिंग लोड करें|Cargar ajustes del diseño|Charger les paramètres|تحميل إعدادات التصميم|নকশার সেটিং লোড|Carregar configurações|Загрузить параметры|Muat pengaturan desain|ڈیزائن کی ترتیبات کھولیں
Export take-off|导出工程量|मात्राएँ निर्यात करें|Exportar cantidades|Exporter les quantités|تصدير الكميات|পরিমাণ রপ্তানি|Exportar quantitativos|Экспорт объёмов|Ekspor kuantitas|مقدار کی رپورٹ ایکسپورٹ کریں
Recheck selection|重新检查选择|चयन फिर जाँचें|Revisar selección|Vérifier la sélection|فحص التحديد|নির্বাচন পুনরায় পরীক্ষা|Verificar seleção|Проверить выделение|Periksa pilihan|انتخاب دوبارہ چیک کریں
Expand all|全部展开|सभी खोलें|Expandir todo|Tout développer|توسيع الكل|সব প্রসারিত করুন|Expandir tudo|Развернуть всё|Perluas semua|سب کھولیں
Collapse all|全部折叠|सभी समेटें|Contraer todo|Tout réduire|طي الكل|সব সংকুচিত করুন|Recolher tudo|Свернуть всё|Ciutkan semua|سب سمیٹیں
Style|样式|शैली|Estilo|Style|النمط|শৈলী|Estilo|Стиль|Gaya|طرز
Presets|预设|पूर्वनिर्धारित|Preajustes|Préréglages|إعدادات مسبقة|পূর্বনির্ধারিত|Predefinições|Шаблоны|Prasetel|پہلے سے طے شدہ
User|用户|उपयोगकर्ता|Usuario|Utilisateur|المستخدم|ব্যবহারকারী|Usuário|Пользовательские|Pengguna|صارف
In Model|模型内|मॉडल में|En el modelo|Dans le modèle|في النموذج|মডেলের মধ্যে|No modelo|В модели|Dalam model|ماڈل میں
Bare lengths|无单位输入|बिना इकाई की लंबाई|Longitudes sin unidad|Longueurs sans unité|أطوال دون وحدة|এককবিহীন দৈর্ঘ্য|Comprimentos sem unidade|Длины без единиц|Panjang tanpa satuan|بغیر اکائی کی لمبائی
Metres|米|मीटर|Metros|Mètres|أمتار|মিটার|Metros|Метры|Meter|میٹر
Feet|英尺|फ़ुट|Pies|Pieds|أقدام|ফুট|Pés|Футы|Kaki|فٹ
Millimetres|毫米|मिलीमीटर|Milímetros|Millimètres|ملليمترات|মিলিমিটার|Milímetros|Миллиметры|Milimeter|ملی میٹر
Inches|英寸|इंच|Pulgadas|Pouces|بوصات|ইঞ্চি|Polegadas|Дюймы|Inci|انچ
Width|宽度|चौड़ाई|Ancho|Largeur|العرض|প্রস্থ|Largura|Ширина|Lebar|چوڑائی
Height|高度|ऊँचाई|Altura|Hauteur|الارتفاع|উচ্চতা|Altura|Высота|Tinggi|اونچائی
Depth|深度|गहराई|Profundidad|Profondeur|العمق|গভীরতা|Profundidade|Глубина|Kedalaman|گہرائی
Length|长度|लंबाई|Longitud|Longueur|الطول|দৈর্ঘ্য|Comprimento|Длина|Panjang|لمبائی
Thickness|厚度|मोटाई|Espesor|Épaisseur|السماكة|পুরুত্ব|Espessura|Толщина|Ketebalan|موٹائی
Offset|偏移|ऑफ़सेट|Desplazamiento|Décalage|الإزاحة|অফসেট|Deslocamento|Смещение|Ofset|آف سیٹ
Radius|半径|त्रिज्या|Radio|Rayon|نصف القطر|ব্যাসার্ধ|Raio|Радиус|Radius|رداس
Spacing|间距|अंतराल|Separación|Espacement|التباعد|ব্যবধান|Espaçamento|Шаг|Jarak|فاصلہ
Angle|角度|कोण|Ángulo|Angle|الزاوية|কোণ|Ângulo|Угол|Sudut|زاویہ
Type|类型|प्रकार|Tipo|Type|النوع|ধরন|Tipo|Тип|Jenis|قسم
Side|侧|पक्ष|Lado|Côté|الجانب|পাশ|Lado|Сторона|Sisi|طرف
Left|左侧|बायाँ|Izquierda|Gauche|يسار|বাম|Esquerda|Слева|Kiri|بائیں
Right|右侧|दायाँ|Derecha|Droite|يمين|ডান|Direita|Справа|Kanan|دائیں
Both sides|两侧|दोनों पक्ष|Ambos lados|Deux côtés|كلا الجانبين|উভয় পাশ|Ambos os lados|Обе стороны|Kedua sisi|دونوں طرف
None|无|कोई नहीं|Ninguno|Aucun|لا شيء|কোনোটিই নয়|Nenhum|Нет|Tidak ada|کوئی نہیں
Road|道路|सड़क|Vía|Route|الطريق|রাস্তা|Via|Дорога|Jalan|سڑک
Name it|名称|नाम दें|Nombre|Nom|الاسم|নাম দিন|Nome|Название|Beri nama|نام دیں
Lane|车道|लेन|Carril|Voie|حارة|লেন|Faixa|Полоса|Lajur|لین
Lanes|车道数|लेन|Carriles|Voies|الحارات|লেন|Faixas|Полосы|Lajur|لین
Lane width|车道宽度|लेन की चौड़ाई|Ancho de carril|Largeur de voie|عرض الحارة|লেনের প্রস্থ|Largura da faixa|Ширина полосы|Lebar lajur|لین کی چوڑائی
Overall|总宽|कुल|Total|Total|الإجمالي|সামগ্রিক|Total|Общая ширина|Keseluruhan|کل
Carriageway|车行道|वाहन मार्ग|Calzada|Chaussée|حارة السير|গাড়ির পথ|Pista|Проезжая часть|Jalur kendaraan|کیریج وے
Sidewalk|人行道|फुटपाथ|Acera|Trottoir|الرصيف|ফুটপাত|Calçada|Тротуар|Trotoar|فٹ پاتھ
Planting|绿化|रोपण|Vegetación|Plantations|التشجير|রোপণ|Vegetação|Озеленение|Tanaman|شجرکاری
Pavement|路面|सड़क सतह|Pavimento|Revêtement|سطح الطريق|সড়কের পৃষ্ঠ|Pavimento|Покрытие|Perkerasan|سڑک کی سطح
Gutter|排水沟|नाली|Cuneta|Caniveau|مزراب|নালা|Sarjeta|Лоток|Talang|نالہ
Green|绿化|हरित|Verde|Vert|أخضر|সবুজ|Verde|Зелёная зона|Hijau|سبز
Verge|绿化带|किनारे की पट्टी|Franja lateral|Bande latérale|حافة جانبية|পাশের ফালা|Faixa lateral|Газон|Jalur tepi|کنارے کی پٹی
Median|中央分隔带|विभाजक|Mediana|Terre-plein|جزيرة وسطية|বিভাজক|Canteiro central|Разделительная полоса|Median|درمیانی پٹی
Parking|停车|पार्किंग|Estacionamiento|Stationnement|مواقف|পার্কিং|Estacionamento|Парковка|Parkir|پارکنگ
Surface|表面|सतह|Superficie|Surface|السطح|পৃষ্ঠ|Superfície|Поверхность|Permukaan|سطح
Crown|路拱|सड़क का उभार|Bombeo|Bombement|تحدب الطريق|রাস্তার উঁচু মধ্যভাগ|Abaulamento|Выпуклость|Kemiringan mahkota|کیمبر
Slope|坡度|ढलान|Pendiente|Pente|الميل|ঢাল|Inclinação|Уклон|Kemiringan|ڈھلوان
Material|材质|सामग्री|Material|Matériau|مادة|উপকরণ|Material|Материал|Material|مادہ
Section|横断面|अनुप्रस्थ काट|Sección|Profil|مقطع|প্রস্থচ্ছেদ|Seção|Сечение|Penampang|کراس سیکشن
Section part|断面部件|काट का भाग|Parte de sección|Élément du profil|جزء المقطع|প্রস্থচ্ছেদের অংশ|Parte da seção|Элемент сечения|Bagian penampang|سیکشن کا حصہ
Area|面积|क्षेत्रफल|Área|Surface|المساحة|ক্ষেত্রফল|Área|Площадь|Luas|رقبہ
Volume|体积|आयतन|Volumen|Volume|الحجم|আয়তন|Volume|Объём|Volume|حجم
Center|中心|केंद्र|Centro|Centre|المركز|কেন্দ্র|Centro|Центр|Tengah|مرکز
Edge|边缘|किनारा|Borde|Bord|الحافة|প্রান্ত|Borda|Край|Tepi|کنارہ
Line|线|रेखा|Línea|Ligne|خط|রেখা|Linha|Линия|Garis|لائن
Dashed|虚线|टूटी रेखा|Discontinua|Discontinue|متقطع|ড্যাশযুক্ত|Tracejada|Штриховая|Putus-putus|ٹوٹی ہوئی
Solid|实线|ठोस|Continua|Continue|متصل|নিরবচ্ছিন্ন|Contínua|Сплошная|Utuh|مسلسل
Gap|间隔|खाली अंतर|Separación|Intervalle|الفجوة|ফাঁক|Intervalo|Промежуток|Celah|خالی فاصلہ
Dash|线段|डैश|Trazo|Trait|شرطة|ড্যাশ|Traço|Штрих|Garis putus|ڈیش
Enabled|启用|सक्रिय|Activado|Activé|مفعّل|সক্রিয়|Ativado|Включено|Aktif|فعال
Automatic|自动|स्वचालित|Automático|Automatique|تلقائي|স্বয়ংক্রিয়|Automático|Автоматически|Otomatis|خودکار
Fixed|固定|निश्चित|Fijo|Fixe|ثابت|নির্দিষ্ট|Fixo|Фиксированный|Tetap|مقرر
Barrier|直立路缘|सीधा कर्ब|Vertical|Verticale|عمودي|খাড়া কার্ব|Vertical|Вертикальный|Tegak|عمودی
Mountable|可跨越路缘|चढ़ने योग्य|Montable|Franchissable|قابل للصعود|অতিক্রমযোগ্য|Transponível|Скошенный|Dapat dilintasi|چڑھنے کے قابل
Flush|齐平|समतल|A ras|Affleurante|مستوٍ|সমতল|Nivelado|Вровень|Rata|ہموار
Channel|排水渠|जल निकासी चैनल|Canal|Canal|قناة|চ্যানেল|Canal|Канал|Saluran|چینل
Grating|格栅|जाली|Rejilla|Grille|شبكة|জালি|Grelha|Решётка|Kisi|جالی
Width mode|宽度模式|चौड़ाई मोड|Modo de ancho|Mode de largeur|وضع العرض|প্রস্থের ধরন|Modo de largura|Режим ширины|Mode lebar|چوڑائی کا طریقہ
Total width|总宽度|कुल चौड़ाई|Ancho total|Largeur totale|العرض الكلي|মোট প্রস্থ|Largura total|Общая ширина|Lebar total|کل چوڑائی
Thickness / offset from line|厚度 / 距线偏移|मोटाई / रेखा से दूरी|Espesor / desplazamiento|Épaisseur / décalage|السماكة / الإزاحة|পুরুত্ব / রেখা থেকে দূরত্ব|Espessura / deslocamento|Толщина / смещение|Ketebalan / ofset garis|موٹائی / لائن سے آف سیٹ
Median width|中央分隔带宽度|विभाजक की चौड़ाई|Ancho de mediana|Largeur du terre-plein|عرض الجزيرة الوسطية|বিভাজকের প্রস্থ|Largura do canteiro|Ширина разделителя|Lebar median|درمیانی پٹی کی چوڑائی
Height × width|高度 × 宽度|ऊँचाई × चौड़ाई|Altura × ancho|Hauteur × largeur|الارتفاع × العرض|উচ্চতা × প্রস্থ|Altura × largura|Высота × ширина|Tinggi × lebar|اونچائی × چوڑائی
Width × thickness|宽度 × 厚度|चौड़ाई × मोटाई|Ancho × espesor|Largeur × épaisseur|العرض × السماكة|প্রস্থ × পুরুত্ব|Largura × espessura|Ширина × толщина|Lebar × ketebalan|چوڑائی × موٹائی
Original help and notes|原始帮助与说明|मूल सहायता और टिप्पणियाँ|Ayuda y notas originales|Aide et notes originales|المساعدة والملاحظات الأصلية|মূল সহায়তা ও নোট|Ajuda e notas originais|Исходная справка|Bantuan dan catatan asli|اصل مدد اور نوٹس
Preview outline|预览轮廓|रूपरेखा पूर्वावलोकन|Vista previa del contorno|Aperçu du contour|معاينة المخطط|রূপরেখার পূর্বরূপ|Prévia do contorno|Предпросмотр контура|Pratinjau garis luar|خاکہ دیکھیں
Draw a road|绘制道路|सड़क खींचें|Dibujar vía|Tracer une route|رسم طريق|রাস্তা আঁকুন|Desenhar via|Нарисовать дорогу|Gambar jalan|سڑک بنائیں
Draw a marking|绘制标线|चिह्न खींचें|Dibujar marca|Tracer un marquage|رسم علامة|চিহ্ন আঁকুন|Desenhar marca|Нарисовать разметку|Gambar marka|نشانی بنائیں
Update attached part only|仅更新连接部分|केवल जुड़ा भाग अद्यतन|Actualizar solo parte conectada|Actualiser la partie connectée|تحديث الجزء المتصل فقط|শুধু সংযুক্ত অংশ হালনাগাদ|Atualizar apenas parte conectada|Обновить связанную часть|Perbarui bagian terhubung saja|صرف منسلک حصہ اپ ڈیٹ کریں
Load its settings|加载其设置|इसकी सेटिंग लोड करें|Cargar sus ajustes|Charger ses paramètres|تحميل إعداداته|এর সেটিং লোড|Carregar suas configurações|Загрузить его параметры|Muat pengaturannya|اس کی ترتیبات کھولیں
Select no road|取消道路选择|सड़क चयन हटाएँ|Quitar selección de vía|Désélectionner la route|إلغاء تحديد الطريق|রাস্তার নির্বাচন সরান|Desmarcar via|Снять выбор дороги|Batalkan pilihan jalan|سڑک کا انتخاب ختم کریں
Road ↔ junction|道路 ↔ 交叉口|सड़क ↔ चौराहा|Vía ↔ intersección|Route ↔ carrefour|طريق ↔ تقاطع|রাস্তা ↔ মোড়|Via ↔ interseção|Дорога ↔ перекрёсток|Jalan ↔ simpang|سڑک ↔ چوراہا
Wider or narrower...|加宽或缩窄…|चौड़ा या संकरा…|Más ancha o estrecha…|Élargir ou rétrécir…|توسيع أو تضييق…|প্রশস্ত বা সরু…|Alargar ou estreitar…|Расширить или сузить…|Lebarkan atau sempitkan…|چوڑا یا تنگ کریں…
Cross-section (vertical scale exaggerated)|横断面（竖向比例放大）|अनुप्रस्थ काट (ऊर्ध्व पैमाना बढ़ाया गया)|Sección transversal (escala vertical exagerada)|Profil en travers (échelle verticale exagérée)|مقطع عرضي (المقياس الرأسي مكبّر)|প্রস্থচ্ছেদ (উল্লম্ব স্কেল বর্ধিত)|Seção transversal (escala vertical exagerada)|Поперечное сечение (вертикаль увеличена)|Penampang (skala vertikal diperbesar)|کراس سیکشن (عمودی پیمانہ بڑھایا گیا)
drawn line|绘制的线|खींची रेखा|línea dibujada|ligne tracée|الخط المرسوم|আঁকা রেখা|linha desenhada|исходная линия|garis gambar|کھینچی ہوئی لائن
Technical notes may remain in English.|技术说明可能保留英文。|तकनीकी टिप्पणियाँ अंग्रेज़ी में रह सकती हैं।|Las notas técnicas pueden seguir en inglés.|Les notes techniques peuvent rester en anglais.|قد تبقى الملاحظات الفنية باللغة الإنجليزية.|কারিগরি নোট ইংরেজিতে থাকতে পারে।|As notas técnicas podem permanecer em inglês.|Технические примечания могут оставаться на английском.|Catatan teknis mungkin tetap dalam bahasa Inggris.|تکنیکی نوٹس انگریزی میں رہ سکتے ہیں۔
'''

ROWS+='''
A face I draw is|绘制面的含义|खींचा गया फलक|La cara representa|La face représente|السطح يمثل|আঁকা পৃষ্ঠটি|A face representa|Что означает грань|Bidang yang digambar|بنائی گئی سطح کی نوعیت
The whole road - curb and walkway inside the line|整条道路：路缘和人行道在线内|पूरी सड़क — कर्ब और फुटपाथ सीमा के अंदर|Toda la vía: bordillo y acera dentro|Toute la route : bordure et trottoir à l’intérieur|الطريق كله: الرصيف داخل الحدود|পুরো রাস্তা — কার্ব ও ফুটপাত সীমানার ভিতরে|Via inteira: meio-fio e calçada dentro|Вся дорога: бордюр и тротуар внутри|Seluruh jalan: kerb dan trotoar di dalam|پوری سڑک: کرب اور فٹ پاتھ حد کے اندر
Just the asphalt - curb and walkway outside it|仅沥青：路缘和人行道在线外|केवल डामर — कर्ब और फुटपाथ बाहर|Solo asfalto: bordillo y acera fuera|Seulement l’asphalte : bordure et trottoir à l’extérieur|الأسفلت فقط: الرصيف خارج الحدود|শুধু পিচ — কার্ব ও ফুটপাত বাইরে|Só asfalto: meio-fio e calçada fora|Только асфальт: бордюр и тротуар снаружи|Hanya aspal: kerb dan trotoar di luar|صرف اسفالٹ: کرب اور فٹ پاتھ باہر
Change the style of the selected road|更改所选道路样式|चयनित सड़क की शैली बदलें|Cambiar estilo de vía seleccionada|Changer le style de la route sélectionnée|تغيير نمط الطريق المحدد|নির্বাচিত রাস্তার শৈলী পরিবর্তন|Alterar estilo da via selecionada|Изменить стиль выбранной дороги|Ubah gaya jalan terpilih|منتخب سڑک کا طرز بدلیں
Repair the selected road or junction|修复所选道路或交叉口|चयनित सड़क या चौराहा सुधारें|Reparar vía o intersección seleccionada|Réparer la route ou le carrefour sélectionné|إصلاح الطريق أو التقاطع المحدد|নির্বাচিত রাস্তা বা মোড় মেরামত|Reparar via ou interseção selecionada|Восстановить выбранную дорогу или перекрёсток|Perbaiki jalan atau simpang terpilih|منتخب سڑک یا چوراہا درست کریں
Style, surface, mouths...|样式、路面、出入口…|शैली, सतह, प्रवेश…|Estilo, superficie, accesos…|Style, surface, accès…|النمط والسطح والمداخل…|শৈলী, পৃষ্ঠ, প্রবেশপথ…|Estilo, superfície, acessos…|Стиль, покрытие, въезды…|Gaya, permukaan, akses…|طرز، سطح، راستے…
Left only|仅左侧|केवल बायाँ|Solo izquierda|Gauche seulement|اليسار فقط|শুধু বাম|Apenas esquerda|Только слева|Kiri saja|صرف بائیں
Right only|仅右侧|केवल दायाँ|Solo derecha|Droite seulement|اليمين فقط|শুধু ডান|Apenas direita|Только справа|Kanan saja|صرف دائیں
Carriageway width|车行道宽度|वाहन मार्ग की चौड़ाई|Ancho de calzada|Largeur de chaussée|عرض مسار الطريق|গাড়ির পথের প্রস্থ|Largura da pista|Ширина проезжей части|Lebar jalur kendaraan|کیریج وے کی چوڑائی
Overall width|道路总宽|कुल चौड़ाई|Ancho total|Largeur totale|العرض الكلي|সামগ্রিক প্রস্থ|Largura total|Общая ширина|Lebar keseluruhan|مجموعی چوڑائی
Road designer|道路设计器|सड़क डिज़ाइनर|Diseñador de vías|Concepteur de routes|مصمم الطرق|রাস্তা নকশাকার|Projetista de vias|Проектирование дорог|Perancang jalan|روڈ ڈیزائنر
TERRAROAD  •  Road designer|TERRAROAD  •  道路设计器|TERRAROAD  •  सड़क डिज़ाइनर|TERRAROAD  •  Diseñador de vías|TERRAROAD  •  Concepteur de routes|TERRAROAD  •  مصمم الطرق|TERRAROAD  •  রাস্তা নকশাকার|TERRAROAD  •  Projetista de vias|TERRAROAD  •  Проектирование дорог|TERRAROAD  •  Perancang jalan|TERRAROAD  •  روڈ ڈیزائنر
'''

ROWS+='''
Additional|附加|अतिरिक्त|Adicional|Supplémentaire|إضافي|অতিরিক্ত|Adicional|Дополнительный|Tambahan|اضافی
Adjustment|调整|समायोजन|Ajuste|Réglage|تعديل|সমন্বয়|Ajuste|Корректировка|Penyesuaian|ترمیم
Batter|斜面|तिरछा भाग|Talud|Fruit|ميل جانبي|পার্শ্বঢাল|Talude|Откос|Kemiringan sisi|ترچھا حصہ
Belt|带|पट्टी|Banda|Bande|حزام|বেল্ট|Faixa|Полоса|Sabuk|پٹی
Block|块|खंड|Bloque|Bloc|كتلة|ব্লক|Bloco|Блок|Blok|بلاک
Bottom|底部|तल|Fondo|Fond|القاع|তল|Fundo|Низ|Dasar|نچلا حصہ
Corner|转角|कोना|Esquina|Angle|زاوية|কোণ|Canto|Угол|Sudut|کونا
Count|数量|संख्या|Cantidad|Nombre|العدد|সংখ্যা|Quantidade|Количество|Jumlah|تعداد
Divided|分隔式|विभाजित|Dividida|Séparée|مقسّم|বিভক্ত|Dividida|Разделённая|Terbagi|تقسیم شدہ
Divider|分隔带|विभाजक|Separador|Séparateur|فاصل|বিভাজক|Separador|Разделитель|Pemisah|تقسیم کنندہ
Drop|下沉|नीचे का अंतर|Desnivel|Décaissement|انخفاض|নিচু অংশ|Desnível|Понижение|Penurunan|نیچے کا فرق
Extend|延伸|बढ़ाएँ|Extender|Prolonger|تمديد|প্রসারিত|Estender|Продлить|Perpanjang|بڑھائیں
Flat|平整|समतल|Plano|Plat|مستوٍ|সমতল|Plano|Плоский|Datar|ہموار
Inset|内缩|अंदर की दूरी|Retranqueo|Retrait|إزاحة داخلية|ভিতরের দূরত্ব|Recuo|Отступ|Jarak masuk|اندرونی فاصلہ
Interval|间隔|अंतराल|Intervalo|Intervalle|الفاصل|ব্যবধান|Intervalo|Интервал|Interval|وقفہ
Level|标高|स्तर|Nivel|Niveau|المنسوب|স্তর|Nível|Уровень|Elevasi|لیول
Lift|抬高|उठान|Elevación|Surélévation|رفع|উত্তোলন|Elevação|Подъём|Kenaikan|بلندی
Marking|标线|चिह्न|Marca|Marquage|علامة|চিহ্ন|Marcação|Разметка|Marka|نشانی
Mirror|镜像|प्रतिबिंब|Reflejar|Symétrie|عكس|প্রতিফলন|Espelhar|Отразить|Cerminkan|عکس
Mode|模式|मोड|Modo|Mode|الوضع|ধরন|Modo|Режим|Mode|طریقہ
Outer|外侧|बाहरी|Exterior|Extérieur|خارجي|বাইরের|Externo|Наружный|Luar|بیرونی
Paint|涂刷|रंग|Pintar|Peinture|طلاء|রং|Pintura|Окраска|Cat|رنگ
Parallel|平行|समानांतर|Paralelo|Parallèle|موازٍ|সমান্তরাল|Paralelo|Параллельный|Sejajar|متوازی
Soil|土壤|मिट्टी|Suelo|Sol|التربة|মাটি|Solo|Грунт|Tanah|مٹی
Stall|车位|पार्किंग स्थान|Plaza|Place|موقف|পার্কিং স্থান|Vaga|Парковочное место|Petak|پارکنگ خانہ
Station|桩号|चैनेज|Estación|Abscisse|المحطة|চেইনেজ|Estaca|Пикет|Stasiun|چینج
Storm water|雨水|वर्षाजल|Agua pluvial|Eaux pluviales|مياه الأمطار|বৃষ্টির পানি|Água pluvial|Ливневая вода|Air hujan|بارش کا پانی
Wall|墙|दीवार|Muro|Paroi|جدار|দেয়াল|Parede|Стенка|Dinding|دیوار
Placement|布置|स्थान व्यवस्था|Ubicación|Disposition|الموضع|স্থাপন|Posicionamento|Расположение|Penempatan|جگہ کا تعین
Support|支撑|आधार|Soporte|Support|دعامة|খুঁটি|Suporte|Опора|Penyangga|سہارا
Design|设计|डिज़ाइन|Diseño|Conception|التصميم|নকশা|Projeto|Проект|Desain|ڈیزائن
Speed|速度|गति|Velocidad|Vitesse|السرعة|গতি|Velocidade|Скорость|Kecepatan|رفتار
Terrain|地形|भूभाग|Terreno|Terrain|التضاريس|ভূখণ্ড|Terreno|Рельеф|Medan|زمین
Bridge|桥梁|पुल|Puente|Pont|جسر|সেতু|Ponte|Мост|Jembatan|پل
Deck|桥面|डेक|Tablero|Tablier|سطح الجسر|ডেক|Tabuleiro|Пролётное строение|Dek|ڈیک
Parapet|护栏墙|मुंडेर|Pretil|Garde-corps|حاجز|প্যারাপেট|Parapeito|Парапет|Parapet|حفاظتی دیوار
Span|跨度|स्पैन|Vano|Portée|البحر|স্প্যান|Vão|Пролёт|Bentang|اسپین
Diameter|直径|व्यास|Diámetro|Diamètre|القطر|ব্যাস|Diâmetro|Диаметр|Diameter|قطر
Crossarm|横担|क्रॉसआर्म|Cruceta|Traverse|ذراع عرضي|ক্রসআর্ম|Cruzeta|Траверса|Lengan silang|کراس آرم
Conductor|导线|चालक तार|Conductor|Conducteur|موصل|পরিবাহী|Condutor|Провод|Konduktor|تار
High voltage|高压|उच्च वोल्टेज|Alta tensión|Haute tension|جهد عالٍ|উচ্চ ভোল্টেজ|Alta tensão|Высокое напряжение|Tegangan tinggi|ہائی وولٹیج
Cut|挖方|कटाई|Corte|Déblai|حفر|কাটা|Corte|Выемка|Galian|کٹائی
Fill|填方|भराई|Relleno|Remblai|ردم|ভরাট|Aterro|Насыпь|Timbunan|بھرائی
Ratio|比例|अनुपात|Relación|Rapport|النسبة|অনুপাত|Razão|Отношение|Rasio|تناسب
Maximum|最大|अधिकतम|Máximo|Maximum|أقصى|সর্বোচ্চ|Máximo|Максимум|Maksimum|زیادہ سے زیادہ
Minimum|最小|न्यूनतम|Mínimo|Minimum|أدنى|সর্বনিম্ন|Mínimo|Минимум|Minimum|کم سے کم
Setback|后退距离|पीछे की दूरी|Retiro|Recul|ارتداد|পিছনের দূরত্ব|Afastamento|Отступ|Jarak mundur|پیچھے کا فاصلہ
Drive side|行驶侧|यातायात का पक्ष|Lado de circulación|Sens de circulation|جهة السير|চলাচলের পাশ|Lado de circulação|Сторона движения|Sisi lalu lintas|ٹریفک کی سمت
Slot|狭槽|खांचा|Ranura|Fente|شق|স্লট|Ranhura|Щель|Slot|سوراخ
Bar|横条|पट्टी|Barra|Barre|قضيب|বার|Barra|Перемычка|Batang|پٹی
Margin|边距|हाशिया|Margen|Marge|هامش|মার্জিন|Margem|Поле|Margin|حاشیہ
Panel|面板|पैनल|Panel|Panneau|لوحة|প্যানেল|Painel|Панель|Panel|پینل
Profile|纵断面|प्रोफ़ाइल|Perfil|Profil|ملف طولي|প্রোফাইল|Perfil|Профиль|Profil|پروفائل
Smoothing|平滑|समतलीकरण|Suavizado|Lissage|تنعيم|মসৃণকরণ|Suavização|Сглаживание|Penghalusan|ہموار کرنا
Passes|次数|बार|Pasadas|Passes|مرات|বার|Passagens|Проходы|Lintasan|بار
Elevation|高程|ऊँचाई|Cota|Altitude|الارتفاع|উচ্চতা|Cota|Отметка|Elevasi|لیول کی اونچائی
Length of approach|引道长度|पहुँच मार्ग की लंबाई|Longitud de acceso|Longueur d’approche|طول الاقتراب|সংযোগ পথের দৈর্ঘ্য|Comprimento de acesso|Длина подхода|Panjang pendekat|اپروچ کی لمبائی
Rise|升高|उठान|Elevación|Montée|ارتفاع|উত্থান|Elevação|Подъём|Kenaikan|اٹھان
North|北向|उत्तर|Norte|Nord|الشمال|উত্তর|Norte|Север|Utara|شمال
Map|地图|मानचित्र|Mapa|Carte|الخريطة|মানচিত্র|Mapa|Карта|Peta|نقشہ
Location|位置|स्थान|Ubicación|Emplacement|الموقع|অবস্থান|Localização|Положение|Lokasi|مقام
Token|令牌|टोकन|Token|Jeton|رمز|টোকেন|Token|Токен|Token|ٹوکن
Asset|资源|एसेट|Recurso|Ressource|أصل|রিসোর্স|Recurso|Ресурс|Aset|اثاثہ
Name|名称|नाम|Nombre|Nom|الاسم|নাম|Nome|Название|Nama|نام
'''

ROWS+='''
Add|添加|जोड़ें|Añadir|Ajouter|إضافة|যোগ|Adicionar|Добавить|Tambah|شامل کریں
Include|纳入|शामिल करें|Incluir|Inclure|تضمين|অন্তর্ভুক্ত|Incluir|Включить|Sertakan|شامل
Amount|程度|मात्रा|Cantidad|Quantité|المقدار|পরিমাণ|Quantidade|Величина|Jumlah|مقدار
Apron|铺砌环带|एप्रन|Delantal|Bande franchissable|منطقة مرصوفة|এপ্রন|Faixa transponível|Фартук|Apron|ایپرن
Arches|拱|मेहराब|Arcos|Arches|أقواس|খিলান|Arcos|Арки|Lengkungan|محرابیں
Connect|连接|जोड़ें|Conectar|Raccorder|ربط|সংযোগ|Conectar|Соединить|Hubungkan|جوڑیں
Box|网格区|बॉक्स|Caja|Quadrillage|شبكة|বক্স|Caixa|Сетка|Kotak|باکس
Branch|支路|शाखा|Ramal|Branche|فرع|শাখা|Ramal|Ответвление|Cabang|شاخ
Speed breaker|减速带|स्पीड ब्रेकर|Resalto|Ralentisseur|مطب|গতিরোধক|Lombada|Лежачий полицейский|Polisi tidur|اسپیڈ بریکر
Bumps|起伏|ऊबड़-खाबड़ भाग|Irregularidades|Bosses|نتوءات|উঁচুনিচু অংশ|Irregularidades|Неровности|Tonjolan|اونچ نیچ
Circulatory|环行道|परिसंचारी मार्ग|Anillo de circulación|Anneau de circulation|مسار دائري|বৃত্তাকার পথ|Anel de circulação|Кольцевая полоса|Jalur sirkulasi|گردشی راستہ
Turning head|尽端回车场|मुड़ने की जगह|Área de giro|Aire de retournement|ساحة دوران|ঘোরার স্থান|Área de retorno|Разворотная площадка|Area putar|موڑنے کی جگہ
Curve|曲线|वक्र|Curva|Courbe|منحنى|বক্ররেখা|Curva|Кривая|Kurva|منحنی
Dark|深色|गहरा|Oscuro|Foncé|داكن|গাঢ়|Escuro|Тёмный|Gelap|گہرا
Degree|度|डिग्री|Grado|Degré|درجة|ডিগ্রি|Grau|Градус|Derajat|درجہ
Entry|入口|प्रवेश|Entrada|Entrée|مدخل|প্রবেশ|Entrada|Въезд|Masuk|داخلہ
Flare|扩口|फैलाव|Abocinamiento|Évasement|اتساع|প্রসারণ|Alargamento|Расширение|Pelebaran|کشادگی
Flatten|平整|समतल करें|Aplanar|Aplanir|تسطيح|সমতল|Aplanar|Выровнять|Ratakan|ہموار کریں
Furniture|道路设施|सड़क उपकरण|Equipamiento vial|Mobilier routier|تجهيزات الطريق|সড়ক সরঞ্জাম|Mobiliário viário|Дорожное оборудование|Perlengkapan jalan|سڑک کا سامان
Grading|整坡|ढलान निर्माण|Explanación|Terrassement|تسوية|ঢাল তৈরি|Terraplenagem|Планировка|Perataan|زمین کی ہمواری
Group|组|समूह|Grupo|Groupe|مجموعة|দল|Grupo|Группа|Grup|گروپ
Clearance|净空|खाली ऊँचाई|Gálibo|Hauteur libre|خلوص|খালি উচ্চতা|Altura livre|Габарит|Ruang bebas|خالی اونچائی
Ignore|忽略|अनदेखा करें|Ignorar|Ignorer|تجاهل|উপেক্ষা|Ignorar|Игнорировать|Abaikan|نظر انداز کریں
Island|交通岛|द्वीप|Isleta|Îlot|جزيرة|দ্বীপ|Ilha|Островок|Pulau|جزیرہ
Transition|过渡|संक्रमण|Transición|Transition|انتقال|রূপান্তর|Transição|Переход|Transisi|منتقلی
Keep|保留|रखें|Mantener|Conserver|إبقاء|রাখুন|Manter|Сохранить|Pertahankan|برقرار رکھیں
Light|浅色|हल्का|Claro|Clair|فاتح|হালকা|Claro|Светлый|Terang|ہلکا
Live|实时|तत्काल|En vivo|En direct|مباشر|তাৎক্ষণিক|Ao vivo|В реальном времени|Langsung|براہ راست
Match|匹配|मिलान|Ajustar|Adapter|مطابقة|মিল|Ajustar|Согласовать|Cocokkan|مطابق
Rebuild|重建|फिर बनाएँ|Reconstruir|Reconstruire|إعادة البناء|পুনর্নির্মাণ|Reconstruir|Перестроить|Bangun ulang|دوبارہ بنائیں
Scale|比例|पैमाना|Escala|Échelle|المقياس|স্কেল|Escala|Масштаб|Skala|پیمانہ
Scope|范围|दायरा|Ámbito|Portée|النطاق|পরিধি|Escopo|Область|Cakupan|دائرہ
Shared|共享|साझा|Compartido|Partagé|مشترك|ভাগ করা|Compartilhado|Общий|Bersama|مشترک
Snap|捕捉|स्नैप|Ajuste|Accrochage|التقاط|স্ন্যাপ|Encaixe|Привязка|Jepret|اسنیپ
Source|来源|स्रोत|Origen|Source|المصدر|উৎস|Origem|Источник|Sumber|ذریعہ
Split|分割|विभाजित करें|Dividir|Diviser|تقسيم|ভাগ|Dividir|Разделить|Pisahkan|تقسیم کریں
Stop|停止|रुकना|Parada|Arrêt|توقف|থামা|Parada|Стоп|Berhenti|رکنا
Straight|直线段|सीधा भाग|Recta|Ligne droite|مستقيم|সোজা অংশ|Reta|Прямая|Lurus|سیدھا حصہ
Stud|突起路标|रोड स्टड|Tacha|Plot réfléchissant|عاكس طريق|রোড স্টাড|Tachão|Дорожный катафот|Paku marka|روڈ اسٹڈ
Superelevation|超高|सुपरएलिवेशन|Peralte|Dévers|الميل العرضي|সুপারএলিভেশন|Superelevação|Вираж|Superelevasi|سپر ایلیویشن
Taper|渐变段|क्रमिक परिवर्तन|Transición gradual|Biseau|تدرج|ক্রমিক পরিবর্তন|Transição gradual|Клиновидный переход|Transisi bertahap|تدریجی تبدیلی
Tolerance|容差|सहनशीलता|Tolerancia|Tolérance|سماحية|সহনশীলতা|Tolerância|Допуск|Toleransi|برداشت
Trim|裁剪|काटें|Recortar|Rogner|قص|ছাঁটাই|Recortar|Обрезать|Pangkas|تراشیں
Truck|卡车|ट्रक|Camión|Camion|شاحنة|ট্রাক|Caminhão|Грузовик|Truk|ٹرک
Turn|转弯|मोड़|Giro|Virage|دوران|মোড়|Retorno|Поворот|Belokan|موڑ
Unchanged|未修改|अपरिवर्तित|Sin cambios|Inchangé|دون تغيير|অপরিবর্তিত|Sem alterações|Без изменений|Tidak berubah|بغیر تبدیلی
Vertices|顶点|शीर्ष बिंदु|Vértices|Sommets|رؤوس|শীর্ষবিন্দু|Vértices|Вершины|Titik sudut|نقاط
Widen|加宽|चौड़ा करें|Ensanchar|Élargir|توسيع|প্রশস্ত|Alargar|Расширить|Lebarkan|چوڑا کریں
Wingwall|翼墙|विंग वॉल|Muro de ala|Mur en aile|جدار جناحي|উইং ওয়াল|Muro de ala|Открылок|Dinding sayap|وِنگ وال
'''

ROWS+='''
Draw / edit road|绘制 / 编辑道路|सड़क बनाएँ / संपादित करें|Dibujar / editar vía|Dessiner / modifier une route|رسم / تعديل طريق|রাস্তা আঁকুন / সম্পাদনা|Desenhar / editar via|Рисовать / редактировать дорогу|Gambar / edit jalan|سڑک بنائیں / ترمیم کریں
Draw a road|绘制道路|सड़क बनाएँ|Dibujar una vía|Dessiner une route|رسم طريق|রাস্তা আঁকুন|Desenhar uma via|Нарисовать дорогу|Gambar jalan|سڑک بنائیں
Show all active options|显示所有可用选项|सभी सक्रिय विकल्प दिखाएँ|Mostrar opciones activas|Afficher les options actives|عرض الخيارات النشطة|সব সক্রিয় বিকল্প দেখান|Mostrar opções ativas|Показать активные параметры|Tampilkan opsi aktif|تمام فعال اختیارات دکھائیں
'''
CATALOGS={code:{} for code,_ in LANGUAGES}
for line in ROWS.strip().splitlines():
    if not line.strip():
        continue
    row=line.split('|')
    if len(row)!=11:
        raise ValueError('Invalid TerraRoad language catalog row: '+row[0])
    for code,text in zip(ORDER,row[1:]):
        CATALOGS[code][row[0]]=text

ALIASES={'centre':'Center','center':'Center','curb':'Curb','kerb':'Curb','walk':'Sidewalk',
         'lane':'Lane','lanes':'Lanes','road':'Road','median':'Median','sidewalk':'Sidewalk',
         'shoulder':'Shoulder','parking':'Parking','verge':'Verge','green':'Green',
         'width':'Width','height':'Height','depth':'Depth','thickness':'Thickness','length':'Length',
         'offset':'Offset','radius':'Radius','spacing':'Spacing','angle':'Angle','type':'Type',
         'side':'Side','slope':'Slope','surface':'Surface','line':'Line','edge':'Edge',
         'dash':'Dash','gap':'Gap','channel':'Channel','grill':'Grating','mat':'Material',
         'auto':'Automatic','enabled':'Enabled','total':'Overall','section':'Section',
         'service':'Service road','pole':'Light poles','signal':'Traffic signals','crossing':'Zebra crossings'}
ALIASES.update({'additional':'Additional','adjust':'Adjustment','batter':'Batter','belt':'Belt','block':'Block',
    'bottom':'Bottom','corner':'Corner','count':'Count','crown':'Crown','divided':'Divided','divider':'Divider',
    'drop':'Drop','extend':'Extend','flat':'Flat','gutter':'Gutter','inset':'Inset','interval':'Interval',
    'level':'Level','lift':'Lift','lines':'Line','mark':'Marking','marks':'Marking','mirror':'Mirror',
    'mode':'Mode','outer':'Outer','paint':'Paint','parallel':'Parallel','soil':'Soil','stall':'Stall',
    'station':'Station','storm':'Storm water','stripe':'Marking','wall':'Wall','placement':'Placement',
    'support':'Support','design':'Design','speed':'Speed','terrain':'Terrain','bridge':'Bridge','deck':'Deck',
    'parapet':'Parapet','span':'Span','diameter':'Diameter','crossarms':'Crossarm','arm':'Crossarm','arms':'Crossarm',
    'conductors':'Conductor','hv':'High voltage','cut':'Cut','fill':'Fill','ratio':'Ratio','max':'Maximum',
    'min':'Minimum','setback':'Setback','drive':'Drive side','slot':'Slot','slots':'Slot','bar':'Bar',
    'margin':'Margin','panel':'Panel','profile':'Profile','smoothing':'Smoothing','smooth':'Smoothing',
    'passes':'Passes','ramp':'Length of approach','rise':'Rise','north':'North','map':'Map','site':'Location',
    'place':'Location','token':'Token','asset':'Asset','name':'Name','at':'','per':'','by':'',
    'cesium':'Cesium','bezier':'Bezier'})
ALIASES.update({'add':'Add','adopt':'Include','amount':'Amount','apron':'Apron','arches':'Arches',
    'attach':'Connect','box':'Box','branch':'Branch','breaker':'Speed breaker','breakers':'Speed breaker',
    'bump':'Bumps','bumps':'Bumps','circulatory':'Circulatory','cul':'Turning head','de':'','sac':'',
    'curve':'Curve','dark':'Dark','degree':'Degree','entry':'Entry','flare':'Flare','flatten':'Flatten',
    'furniture':'Furniture','grade':'Grading','group':'Group','headroom':'Clearance','ignore':'Ignore',
    'island':'Island','join':'Transition','joins':'Transition','junction':'Junctions','junctions':'Junctions',
    'keep':'Keep','least':'Minimum','light':'Light','live':'Live','matches':'Match','poles':'Light poles',
    'rebuild':'Rebuild','roads':'Road','scale':'Scale','scope':'Scope','share':'Shared','shoulders':'Shoulder',
    'snap':'Snap','source':'Source','split':'Split','stand':'Placement','stop':'Stop','stops':'Stop',
    'straight':'Straight','stud':'Stud','studs':'Stud','style':'Style','superelevation':'Superelevation',
    'taper':'Taper','tolerance':'Tolerance','trim':'Trim','truck':'Truck','turn':'Turn','turns':'Turn',
    'u':'U','unchanged':'Unchanged','vertices':'Vertices','widen':'Widen','wingwall':'Wingwall'})


def translate(text,language='en'):
    if language=='en' or not text:
        return text
    catalog=CATALOGS.get(language,{})
    if text.startswith('■ '):
        return '■ '+translate(text[2:],language)
    if text in catalog:
        return catalog[text]
    # Stable short compound labels and generated part names. Long original
    # explanatory prose is deliberately left intact rather than word-swapped.
    if len(text)<65:
        words=text.split()
        translated=[]
        hits=0
        for word in words:
            key=ALIASES.get(word.lower(),word)
            replacement=catalog.get(key)
            if replacement:
                hits+=1
            translated.append(replacement or word)
        if hits==len(words):
            return ' '.join(translated)
    return text


def field_label(keys,fallback,language):
    direct=translate(fallback,language)
    if direct!=fallback or language=='en':
        return direct
    # Unknown authored sentence labels retain the English original; it remains
    # available as a tooltip. The data-driven short field names use translated
    # known terms where every component is in the glossary.
    result=[]
    for key in keys:
        tokens=key.split('_')
        if any(token not in ALIASES for token in tokens):
            return fallback
        words=[ALIASES[token] for token in tokens if ALIASES[token]]
        result.append(' '.join(translate(word,language) for word in words))
    return ' / '.join(result)
