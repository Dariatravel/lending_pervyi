# Короткие ссылки на объекты

Обновлено: 2026-10-15. Объектов: 240.

Машиночитаемая версия: `data/korotkie-ssylki.json`.

## Откуда это берётся

Источник правды — Google-таблица «БАЗА - отели и квартиры», лист СОЦСЕТИ,
столбец «Сайт». Этот файл — её слепок, чтобы ссылки были под рукой
прямо в репозитории и не приходилось каждый раз лезть в таблицу.

Сам короткий адрес — это страница-заглушка на сайте с тегом canonical
на настоящую страницу объекта. HTTP-переадресации нет, поэтому обычный
запрос такой адрес не «разворачивает»: чтобы узнать, куда он ведёт,
надо скачать заглушку и прочитать canonical.

## Как обновить этот файл

Пересобрать из таблицы скриптом, который лежит рядом с подборками:
`~/Documents/ПОДБОРКИ/` — там же `korotkie_ssylki_obektov.json`,
соответствие «длинный адрес страницы -> короткий», его использует
`rebuild_site_podborki_ab_rf.py` при сборке подборок.

Когда появляется новый объект: завести для него короткую страницу на сайте,
вписать адрес в столбец «Сайт» таблицы, после этого обновить этот файл.

## Исправление 11 адресов — 15.10.2026

Все 11 коротких адресов опубликованы. Проверены на `abhazbereg.ru` и
`абхазберег.рф`: HTTP 200, переходы ведут на правильные страницы. Старые
длинные адреса сохранены. В таблице «СОЦСЕТИ» обновлены ровно эти 11 ячеек
столбца H, скрытые и красные строки не затронуты. Коммит `db6762591`.

## Объектов без ссылки на сайт: 1

- "МАНСАРДА" квартира 2-к

## Все объекты

| Объект | Короткая ссылка |
|---|---|
| "АБАЗА" мини-отель | `abhazbereg.ru/abaza` |
| "АБЫРЛАШ" отель на пляже | `abhazbereg.ru/abyrlash` |
| "АВРОРА ИНН ГАГРА" отель | `abhazbereg.ru/avrora-inn-novyy` |
| "АДУНЕЙ" гостевой дом | `abhazbereg.ru/aduney` |
| "АИША" отель с бассейнами | `abhazbereg.ru/aisha` |
| "АКВА" отель с бассейном и завтраками | `abhazbereg.ru/akva` |
| "АКВАМАРИН" дом под ключ | `abhazbereg.ru/akvamarin` |
| "АКВАРЕЛЬ" три 2к квартиры | `abhazbereg.ru/akvarel-tri` |
| "АКИРА" квартира 2к | `abhazbereg.ru/akira` |
| "АЛЕКСАНДРА" отель с питанием и бассейном у моря | `abhazbereg.ru/aleksandra` |
| "АЛЕКСАНДРИЯ" домики | `abhazbereg.ru/aleksandriya` |
| "АЛМА" домики на берегу | `abhazbereg.ru/alma` |
| "АМЗАРА" отель c винодельней у заповедника | `abhazbereg.ru/amzara` |
| "АМИНА" дом под ключ | `abhazbereg.ru/amina` |
| "АМОР" апартаменты с кухней и бассейном | `abhazbereg.ru/amor` |
| "АМОР" домики с бассейном | `abhazbereg.ru/amor-domiki` |
| "АНАИТ" гостевой дом | `abhazbereg.ru/anait` |
| "АНИСА" квартира 1-к | `abhazbereg.ru/anisa` |
| "АНТАА" гостиница у пляжа | `abhazbereg.ru/antaa` |
| "АПРА" гостевой дом на пляже | `abhazbereg.ru/apra` |
| “АПСА” парк-отель | `abhazbereg.ru/apsa-park` |
| "АРАШ" домики у соснового пляжа | `abhazbereg.ru/arash` |
| "АРГО" квартира 1-к | `abhazbereg.ru/argo` |
| "АРИНА" мини-отель | `abhazbereg.ru/arina` |
| "АРТ ОТЕЛЬ" с питанием и бассейном | `abhazbereg.ru/art` |
| "АСЕЛИНА" коттеджи и студия с кухней | `abhazbereg.ru/aselina` |
| "АССИР ПИЦУНДА" гостевой дом в центре | `abhazbereg.ru/assir-pitsunda` |
| "АССИР" гостевой дом | `abhazbereg.ru/assir` |
| "АТМОСФЕРНАЯ" квартира 2к | `abhazbereg.ru/atmosfernaya` |
| "АШТА ДУ" гостевой дом | `abhazbereg.ru/ashta-du` |
| "БАГРИПШ" домики на берегу с питанием | `abhazbereg.ru/bagripsh` |
| "БАНАН И ФУНДУК" гостевой дом | `abhazbereg.ru/banan-i-funduk` |
| "БАРНАБА" гостевой дом | `abhazbereg.ru/barnaba` |
| "БЕЛАЯ ДАЧА" отель с питанием | `abhazbereg.ru/belaya-dacha` |
| "БЕЛАЯ ЛОШАДЬ" эко-комплекс с бассейном и собственной конюшней | `abhazbereg.ru/belaya-loshad` |
| "БЕЛАЯ РЕЧКА" гостевой дом с кафе | `abhazbereg.ru/belaya-rechka` |
| "БЕЛЫЙ ДОМ" домики и апартаменты | `abhazbereg.ru/belyy` |
| “БЕЛЬВЕДЕР” гостевой дом | `abhazbereg.ru/belveder` |
| "БЕРЕГ СВЯТОЙ СОФИИ" отель | `abhazbereg.ru/bereg-svyatoy-sofii` |
| "БИ ХЭППИ" апарт-отель | `abhazbereg.ru/bi-heppi-apart` |
| "БИОСФЕРА" домики у Кындыгского источника | `abhazbereg.ru/biosfera` |
| "БИРЮЗА" апартаменты 60 кв.м | `abhazbereg.ru/biryuza` |
| "БЛАГО-ДАРЮ" отель | `abhazbereg.ru/blago-daryu` |
| "БЛЭК СИ" отель с бассейном и питанием | `abhazbereg.ru/blek-si` |
| "БОНЖУР" мини-отель | `abhazbereg.ru/bonzhur` |
| "БОХО" коттеджи у моря с бассейном и баней | `abhazbereg.ru/boho` |
| "БРИГАНТИНА" гостевой дом | `abhazbereg.ru/brigantina` |
| "БРИЗ" домики на берегу | `abhazbereg.ru/briz` |
| "БУГЕНВИЛЛЕЯ" отель с бассейном | `abhazbereg.ru/bugenvilleya` |
| "БУНГАЛО" глэмпинг в горах | `abhazbereg.ru/bungalo` |
| "В ГОСТЯХ У БЕЛОЧКИ" домики и номера | `abhazbereg.ru/v-gostyah-u-belochki` |
| "В СИНОПЕ" домики | `abhazbereg.ru/v-sinope` |
| "ВИКТОРИЯ" квартира 2-к | `abhazbereg.ru/viktoriya` |
| "ВИЛЛА ЛЕОНА" люкс-отель | `abhazbereg.ru/villa-leona` |
| "ВИЛЛА ЛЮБОВЬ" выход из отеля сразу на пляж | `abhazbereg.ru/villa-lyubov` |
| "ВИЛЛА МАГНОЛИЯ" эко-отель с завтраками | `abhazbereg.ru/villa-magnoliya` |
| "ВИЛЛА СУХУМ" коттеджи с кухней | `abhazbereg.ru/villa-suhum` |
| "ВИСТА МАРЕ" первый этаж дома под ключ с бассейном | `abhazbereg.ru/vista-mare-1-etazh` |
| «ВИСТА МАРЕ» второй этаж дома под ключ с бассейном | `abhazbereg.ru/vista-mare-2-etazh` |
| “ВОСХОДЯЩАЯ ЗВЕЗДА” отель с бассейном | `abhazbereg.ru/voshodyaschaya-zvezda` |
| "ГРАНТ" апартаменты | `abhazbereg.ru/grant-apartamenty` |
| "ГРАНТ" домики | `abhazbereg.ru/grant-kompleks` |
| "ГРАНТ" отель | `abhazbereg.ru/grant` |
| "ГРАСС" коттеджи в горах Абхазии | `abhazbereg.ru/grass-novyy-god` |
| “ГРАФИТ ХАУС” гостевой дом с бассейном | `abhazbereg.ru/grafit-haus` |
| "ГРЕЙС" квартира | `abhazbereg.ru/greys` |
| "ГРИН ВИЛЛАДЖ" домики | `abhazbereg.ru/grin-villadzh` |
| "ГРИН ХАУС" домики | `abhazbereg.ru/grin-haus` |
| "ДАВИД" гостевой дом | `abhazbereg.ru/david` |
| "ДАМИРА" отель в центре города | `abhazbereg.ru/damira` |
| "ДАНЕЛЯН" семейный отель со столовой | `abhazbereg.ru/danelyan-semeynyy` |
| "ДЕЛЬФИН" домики | `abhazbereg.ru/delfin` |
| "ДЕМИ МОККО" - два уютных домика | `abhazbereg.ru/demi-mokko-dva-domika` |
| "ДИАР" домики с бассейном | `abhazbereg.ru/diar` |
| "ДОМИКИ У МАРИНЫ" отдых у моря | `abhazbereg.ru/domiki-u-mariny` |
| "ДУЭТ МОККО" номера | `abhazbereg.ru/duet-mokko` |
| “ДЫШИ ГЛУБЖЕ” домики в горах | `abhazbereg.ru/dyshi-glubzhe` |
| "ДЮНА" домики | `abhazbereg.ru/dyuna` |
| "ЖАСМИН" мини-отель | `abhazbereg.ru/zhasmin` |
| "ЖЕМЧУЖИНА" гостевой дом | `abhazbereg.ru/zhemchuzhina` |
| "ЗЕЛЕНЫЙ ДВОРИК" домики и номера | `abhazbereg.ru/zelenyy-dvorik` |
| "ЗОЛОТАЯ ВЕРАНДА" гостевой дом | `abhazbereg.ru/zolotaya-veranda` |
| "ИНКИТ РЕЗОРТ" афреймы | `abhazbereg.ru/inkit-rezort-afreymy` |
| "ИРСЕН" домики в Алахадзы | `abhazbereg.ru/irsen` |
| "КАВО ДЕ БУКСО" домики | `abhazbereg.ru/kavo-de-bukso` |
| "КАМЕЛИЯ" домики | `abhazbereg.ru/kameliya` |
| "КАМИЛЛА" квартира 2-к | `abhazbereg.ru/kamilla` |
| "КАРАЛИНА" апартаменты | `abhazbereg.ru/karalina` |
| "КАРИН" гостевой дом | `abhazbereg.ru/karin` |
| "КАШТАК" - домики в зеленом уголке | `abhazbereg.ru/kashtak` |
| "КВАРЦ" домики | `abhazbereg.ru/kvarts` |
| "КИАРАЗ РЕЗОРТ" гостевой комплекс с бассейном | `abhazbereg.ru/kiaraz-rezort` |
| "КИПАРИСОВАЯ" квартира 1-к | `abhazbereg.ru/kiparisovaya` |
| "КИРА" гостевой комплекс | `abhazbereg.ru/kira` |
| "КЛАССИКА" квартира 2-к | `abhazbereg.ru/klassika` |
| "КРЫЛЬЯ" домики видовые двухкомнатные | `abhazbereg.ru/krylya` |
| "КУРОРТНАЯ" квартира 2-к | `abhazbereg.ru/kurortnaya` |
| "ЛАВАНДА" вилла с бассейном | `abhazbereg.ru/lavanda` |
| "ЛАДАРИЯ" квартира 1к | `abhazbereg.ru/ladariya` |
| "ЛАЗУРИТ" новый отель | `abhazbereg.ru/lazurit-novyy` |
| "ЛАЗУРНЫЙ БЕРЕГ" бутик-отель с питанием | `abhazbereg.ru/lazurnyy-bereg-butik` |
| “ЛАЙМ” мини-отель с бассейном у заповедника | `abhazbereg.ru/laym` |
| "ЛАТТЕ" квартира 1к | `abhazbereg.ru/latte` |
| "ЛЕОН" коттеджи в тихом районе | `abhazbereg.ru/leon` |
| "ЛЕТНЯЯ" квартира 3к | `abhazbereg.ru/letnyaya` |
| "ЛЕТО" квартира 2к | `abhazbereg.ru/leto` |
| "ЛИЛИЯ" отель | `abhazbereg.ru/liliya-uyutnyy` |
| "ЛИМАРИ" домики | `abhazbereg.ru/limari` |
| "ЛИМОН" отель | `abhazbereg.ru/limon` |
| "ЛК-ОТЕЛЬ" с бассейном | `abhazbereg.ru/lk` |
| "ЛНД" гостевой дом в Синопе | `abhazbereg.ru/lnd` |
| "МАГНОЛИЯ" квартира 3-к | `abhazbereg.ru/magnoliya` |
| "МАДЛЕНА" домики | `abhazbereg.ru/madlena` |
| "МАЛЬБЕК" отель | `abhazbereg.ru/malbek` |
| "МАНДАРИН" отель у соснового пляжа в Лдзаа с завтраками | `abhazbereg.ru/mandarin` |
| "МАНДАРИНОВЫЙ ДВОРИК" дом под ключ | `abhazbereg.ru/mandarinovyy-dvorik` |
| "МАНОН" отель со сказочным видом | `abhazbereg.ru/manon` |
| “МАРТА” гостевые номера | `abhazbereg.ru/marta-gostevye` |
| "МАЯК" гостевой дом | `abhazbereg.ru/mayak` |
| "МЕЛАНА" квартира 3-к | `abhazbereg.ru/melana` |
| "МЕЛОДИ" домики | `abhazbereg.ru/melodi-eko` |
| "МЕЧТА" апартаменты у моря | `abhazbereg.ru/mechta` |
| "МЗИЯ" мини-отель | `abhazbereg.ru/mziya-gostevye` |
| "МИКА" гостевой дом эконом | `abhazbereg.ru/mika` |
| "МИМИ" домики с видом на горы | `abhazbereg.ru/mimi` |
| "МИМОЗА" квартира 3-к | `abhazbereg.ru/mimoza` |
| "МИРА" дом под ключ | `abhazbereg.ru/mira` |
| "МИРА" домики и номера у озера | `abhazbereg.ru/mira-domiki` |
| "МИРАНО" гостевой дом | `abhazbereg.ru/mirano` |
| "МИРАСЛАВА" мини-отель | `abhazbereg.ru/miraslava` |
| "МОККО БРИЗ" два домика | `abhazbereg.ru/mokko-briz-dva-domika` |
| "МОККО ГРЕЙ" апартаменты 1к | `abhazbereg.ru/mokko-grey` |
| "МОККО" апартаменты | `abhazbereg.ru/mokko` |
| "МОН АМУР" квартира 1-к | `abhazbereg.ru/mon-amur` |
| "МОНРО" квартира 2-к | `abhazbereg.ru/monro` |
| “МОРЕ-МОРЕ” гостевой комплекс | `abhazbereg.ru/more-more` |
| "МОРЕОН" домики | `abhazbereg.ru/moreon-domiki` |
| "МОРЕОН" квартира 2-к | `abhazbereg.ru/moreon` |
| "МОРСКАЯ ЛАГУНА" гостиница с завтраками | `abhazbereg.ru/morskaya-laguna` |
| "МУЛБЕРРИ" с бассейном и кафе | `abhazbereg.ru/mulberri` |
| "НА ВРЕМЯ В РАЮ" полдома под ключ | `abhazbereg.ru/na-vremya-v-rayu` |
| "НА ВЫСОТЕ" квартира 2-к | `abhazbereg.ru/na-vysote` |
| "НА ПЛЯЖЕ" квартира 3К видовая | `abhazbereg.ru/na-plyazhe` |
| "НАСТА" апартаменты | `abhazbereg.ru/nasta` |
| "НАСТА" гостевой дом | `abhazbereg.ru/nasta-gostevoy` |
| "НЕАНИЛА" эко-домики | `abhazbereg.ru/neanila-eko` |
| "НЕБОСВОД" афрейм в уединенном месте | `abhazbereg.ru/nebosvod` |
| “НИКОЛЬ” гостевой дом | `abhazbereg.ru/nikol` |
| "НИКОПСИЯ" домики | `abhazbereg.ru/nikopsiya` |
| "НОННА" квартира 2к | `abhazbereg.ru/nonna` |
| "ОАЗИС" апартаменты с кухней | `abhazbereg.ru/oazis-apartamenty` |
| "ОАЗИС" вилла в Сухуме | `abhazbereg.ru/oazis` |
| "ОЛИВА" домики | `abhazbereg.ru/oliva` |
| "ПАЛЬМА" гостевой дом | `abhazbereg.ru/palma` |
| "ПАЛЬМА" квартира 3-к | `abhazbereg.ru/palma-kvartira` |
| ПАНСИОНАТ «БАГРИПШ» (ГЛАВНЫЙ КОРПУС) | `abhazbereg.ru/bagripsh-glavnyy` |
| ПАНСИОНАТ «БАГРИПШ» (КОРПУС «АДЕЛЬ») | `abhazbereg.ru/bagripsh-adel` |
| ПАНСИОНАТ «БАГРИПШ» (НОВЫЙ КОРПУС) | `abhazbereg.ru/bagripsh-novyy` |
| "ПАРКОВАЯ" квартира 2-к | `abhazbereg.ru/parkovaya` |
| "ПАРУС" видовой отель с бассейном и столовой | `abhazbereg.ru/parus-vidovoy` |
| "ПЕГАС" | `abhazbereg.ru/pegas` |
| "ПЕРЛ" доп под ключ | `abhazbereg.ru/perl` |
| “ПЕСЧАНЫЙ БЕРЕГ” апартаменты | `abhazbereg.ru/peschanyy-bereg` |
| "ПИОН" гостевой дом | `abhazbereg.ru/pion` |
| "ПИТИУНТ" квартира 4к | `abhazbereg.ru/pitiunt` |
| "ПИЦУНДА" отель | `abhazbereg.ru/pitsunda-otel` |
| "ПЛЯЖНЫЙ КОМПЛЕКС 151" на берегу | `abhazbereg.ru/plyazhnyy` |
| "ПРОСТОРНАЯ" квартира 5к | `abhazbereg.ru/prostornaya` |
| "ПТИЧКА" эко-домики с бассейном | `abhazbereg.ru/ptichka-eko` |
| "ПШАДА" отель с питанием у соснового пляжа | `abhazbereg.ru/pshada` |
| "РАДОНОВЫЙ ИСТОЧНИК" отель в горах Ткуарчалский район, | `abhazbereg.ru/radonovyy-istochnik` |
| "РАЙСКИЙ БЕРЕГ" мини-отель | `abhazbereg.ru/rayskiy-bereg` |
| "РАНЧО ЭЛИВЕЛ" мини-отель | `abhazbereg.ru/rancho-elivel` |
| "РД-ОТЕЛЬ" в Гагре | `abhazbereg.ru/rd` |
| "РЕГИНА" ОТЕЛЬ (ВТОРОЙ КОРПУС) | `abhazbereg.ru/regina` |
| "РЕГИНА" ОТЕЛЬ (ПЕРВЫЙ КОРПУС) | `abhazbereg.ru/regina-pervyy-korpus` |
| "РЕЛАКС ДОМ" домики | `abhazbereg.ru/relaks` |
| "РИВЬЕРА" гостиница видовая | `abhazbereg.ru/rivera-gostinitsa` |
| "РИВЬЕРА" домики на пляже | `abhazbereg.ru/rivera` |
| "РИММА" две квартиры 1-к с кухней | `abhazbereg.ru/rimma-dve` |
| "РИТА" домики и апартаменты с питанием | `abhazbereg.ru/rita` |
| «РОЯЛ РИВЬЕРА» отель с бассейном и питанием | `abhazbereg.ru/royal-rivera` |
| "РУСАНА" эко-домики | `abhazbereg.ru/rusana-eko` |
| "САБИНА" домики у моря | `abhazbereg.ru/sabina` |
| "САМШИТ" домики и номера у заповедника | `abhazbereg.ru/samshit` |
| "САН АМРА" новый отель на пляже | `abhazbereg.ru/san-amra-lyuks` |
| "САН СЕБАСТИАН" домики с бассейном | `abhazbereg.ru/san-sebastian` |
| "САНДИ ХАУС" коттеджный комплекс с бассейном | `abhazbereg.ru/sandi-haus-kottedzhnyy` |
| "САННИ ХОУМ" домики с бассейном | `abhazbereg.ru/sanni-houm` |
| "САНРАЙЗ" гостевой дом с завтраками | `abhazbereg.ru/sanrayz` |
| "САНРЭЙ" гостевой дом | `abhazbereg.ru/sanrey` |
| "САНСЕТ" квартира видовая 2-к | `abhazbereg.ru/sanset` |
| "САЯ" домики | `abhazbereg.ru/saya` |
| "СВЕТЛЫЙ ДВОРИК" гостевой дом эконом | `abhazbereg.ru/svetlyy-dvorik` |
| "СЕКРЕТ ГАРДЕН" апартаменты | `abhazbereg.ru/sekret-garden` |
| "СИА ЛЕНД" база отдыха | `abhazbereg.ru/sia-lend` |
| "СИЗОН" гостевой дом | `abhazbereg.ru/sizon` |
| “СИМОНА” гостевой дом | `abhazbereg.ru/simona` |
| "СИМСИМ" гостевой дом | `abhazbereg.ru/simsim` |
| "СИНОП ХАУС" коттеджи | `abhazbereg.ru/sinop-haus` |
| "СИРИУС" | `abhazbereg.ru/sirius` |
| "СИСАЙД" домики | `abhazbereg.ru/sisayd` |
| "СИТИ ГАГРА" квартира 2-к | `abhazbereg.ru/siti-gagra` |
| "СОЗВЕЗДИЕ" мини-отель | `abhazbereg.ru/sozvezdie` |
| "СОЛНЕЧНАЯ" квартира 2-к | `abhazbereg.ru/solnechnaya` |
| "СОЛУНА" домики и номера | `abhazbereg.ru/soluna` |
| "СОСНОВАЯ" квартира 1к | `abhazbereg.ru/sosnovaya` |
| “СОФИЯ” отель у соснового пляжа | `abhazbereg.ru/sofiya` |
| "СТАРЫЙ ПРИЧАЛ" гостевой дом у моря | `abhazbereg.ru/staryy-prichal` |
| "СТУДИО САН АМРА" студия на пляже | `abhazbereg.ru/studio-san-amra` |
| "СУХУМ" дом под ключ | `abhazbereg.ru/suhum-dom` |
| "ТЕРРА РИВЬЕРА" эко-комплекс | `abhazbereg.ru/terra-rivera-eko` |
| "ТИС" коттеджи у заповедника | `abhazbereg.ru/tis-kottedzhi` |
| "ТИС" мини-отель у заповедника | `abhazbereg.ru/tis` |
| "ТИХАЯ БУХТА" апартаменты на горы | `abhazbereg.ru/tihaya-buhta` |
| "ТИХАЯ ОБИТЕЛЬ" дом под ключ | `abhazbereg.ru/tihaya-obitel` |
| "ТИХИЙ ЗАКАТ" домики с бассейном | `abhazbereg.ru/tihiy-zakat` |
| "ТРИО" номер на пляже | `abhazbereg.ru/trio-nomer-na-plyazhe` |
| "ФАЗЕНДА" двухэтажные коттеджи с бассейном и питанием | `abhazbereg.ru/fazenda-dvuhetazhnye` |
| "ФАЗЕНДА" отель с бассейном и питанием | `abhazbereg.ru/fazenda` |
| "ФЕМЕЛИ" база отдыха с бассейном и питанием | `abhazbereg.ru/femeli` |
| "ФЕНИКС" дом под ключ | `abhazbereg.ru/feniks` |
| "ФЛАМИНГО" гостевой дом | `abhazbereg.ru/flamingo` |
| "ФЛОРА" частный домик | `abhazbereg.ru/flora` |
| "ФУЛЛ ХАУС" домики с бассейном | `abhazbereg.ru/full-haus` |
| "ФЬЮЖН" три домика с лаунж-зоной | `abhazbereg.ru/fyuzhn` |
| "ХЭППИ ЛЭНД" домики двухэтажные | `abhazbereg.ru/heppi-lend` |
| "ЦАРСКОЕ СЕЛО АНХУА" коттеджи | `abhazbereg.ru/tsarskoe-selo-anhua` |
| "ЦЕНТРАЛЬНЫЙ" дом под ключ | `abhazbereg.ru/tsentralnyy` |
| “ЧЕГЕМ” гостевой дом | `abhazbereg.ru/chegem` |
| "ЧЕРНОМОРСКАЯ-1" квартира 2-к | `abhazbereg.ru/chernomorskaya-1` |
| "ЧЕРНОМОРСКАЯ-2" квартира 2-к | `abhazbereg.ru/chernomorskaya` |
| "ЭДЕМ" домики | `abhazbereg.ru/edem` |
| "ЭКО ХАУС ПИТИУНТ" домики с бассейном | `abhazbereg.ru/eko-haus-pitiunt` |
| "ЭКОХОУМ" коттедж-отель | `abhazbereg.ru/ekohoum` |
| "ЭСМА" - студия | `abhazbereg.ru/esma-studiya` |
| "ЭСМА" домики с бассейном в Гудауте | `abhazbereg.ru/esma` |
| "ЮЖНОЕ СЧАСТЬЕ" домики с бассейном и завтраками | `abhazbereg.ru/yuzhnoe-schaste` |
| "ЮЖНОЕ УТРО" двухкомнатные апартаменты | `abhazbereg.ru/yuzhnoe-utro` |

## «Виста Маре»: отдельный дом

Страница с 9 фото и видео собрана из Telegram-поста 5382. Короткий
адрес: `abhazbereg.ru/vista-mare-dom`. Строка источника в таблице: 69.
Общие отзывы без подтверждённой связи с объектом на страницу не добавляются.
