Jag har nu gått igenom rådata från reflektorpromenaden (TX1, 8 RX) och räknat om själv. Kort version: av de ca 4 dB som mätningen låg över modellen (36,6 mot 32,7) kommer 1,3 dB från att reflektorn är starkare än antaget och ca 1,2 dB troligen från valet av brusreferens. Kvar blir ca 1,2 dB till mätningens fördel, eller upp till 2,4 dB om bruset i bortre fjärdedelen visar sig vara rätt referens (se nedan). Den återstående skillnaden ligger kanske inom den samlade osäkerheten (reflektorns RCS, geometrin, diverse databladsvärden, etc) och indikerar inget uppenbart behov av att justera modellen. På kort avstånd, där markreflexerna bör påverka minst (och spridningen också är minst), ligger mätningen dessutom praktiskt taget på modellen.

**Referenspunkt:** SNR per RX-kanal (linjärt medel över de 8 kanalerna, ingen koherent summering), med brus skattat på samma avstånd och nära samma doppler i CPI:er där reflektorn var någon annanstans. R⁻⁴-normerat till 100 m och 10 dBsm blir det 33,9 dB för alla 39 CPI:er på väg in (17–51 m). Modellen ger 32,7 dB, samma som din handräkning (32,6).

**Varifrån de 4 dB kom:**
```
Rapporten (33 utvalda punkter)             36,6 dB
Min reproduktion (37 punkter)              +0,4
Magnitudsumma -> medel av RX-effekt        -0,3
Brus i bortre fjärdedelen -> vid målet     -1,2
Reflektorns RCS 10 -> 11,27 dBsm           -1,3
Alla 39 CPI:er på väg in                   -0,2
Resultat                                   33,9 dB  (modell 32,7)
```
Brusreferensen är den mest osäkra posten. Brusgolvet vid målets beatfrekvenser (1–3 MHz) ligger 1–1,4 dB över bortre fjärdedelen, stabilt under hela inspelningen och okorrelerat mellan RX-kanalerna. Det beter sig alltså som mottagarbrus, inte som fasbrus från läckage eller närliggande reflexer, som skulle vara gemensamt för kanalerna. Är det förstärkningsformen i IF-kedjan påverkas signalen lika mycket, och då är det lokala bruset rätt referens. Databladets NF (med TX av) skiljer bara 0,3 dB mellan 1 och 10 MHz, vilket talar för det. Är det i stället ett brustillskott vid låga frekvenser hamnar mätningen på 35,1 dB, ca 2,4 dB över modellen. En mätning med TX av skulle avgöra, eftersom en förstärkningsform finns kvar även då.

**Geometri:** Mellan 17 och 27 m ligger punkterna tätt, 32,8 ± 0,6 dB, alltså praktiskt taget på modellen. Längre ut ökar spridningen, med de flesta punkterna över modellen och enstaka djupa dippar, vilket är typiskt för markreflexer. Hur högt satt radarn, och bar du reflektorn ungefär i midjehöjd? På väg ut är returen ca 12 dB svagare efter avståndskorrektion – hur bar du reflektorn då?

**Brusplatå i doppler:** Den starka reflektorn ger en bred brusplatå över hela dopplerbandet på sitt eget avstånd. Den skalar mycket precist som målets effekt × avstånd² (figur 2), vilket pekar på ett fasfel per chirp som är proportionellt mot löptiden, t.ex. ett frekvensfel som varierar från chirp till chirp. Det motsvarar ca 17 kHz rms, samma nivå och skalning som i utomhusmätningarna från 22/9 med 400 och 800 MHz. Där syntes också att störningen är fasdominerad och gemensam för RX-kanalerna, och 8–12 dB starkare än vad databladets fasbrus ger. Gemensam fas för alla kanaler hamnar längs målets styrvektor, så det kan mycket väl vara samma sak som gav den signalberoende komponenten i mätkammaren. För känsligheten mot svaga mål spelar det ingen roll, men om det följer med till produkten och skalningen håller växer fasfelet linjärt med avståndet: upp till ca 0,7 rad vid 1 km, vilket skulle ge upp till runt 2 dB koherent förlust och en rejäl platå kring starka mål. Värt att förstå tidigt.

Ett enkelt och nyttigt test vore några captures rakt ut över E6:an genom öppet fönster från kontoret mot den byggnad som vi sett ger väldigt starkt eko, en med promenadens vågform (100 MHz, räcker till ca 380 m) och en med halva lutningen. Om R²-skalningen håller bör platån ligga 20 dB högre relativt toppen vid 300 m än vid 30 m.

**Koherent summa:** Din koherenta summa på 41,6 dB blir med samma brus- och RCS-korrektioner grovt 39 dB, dvs ca 5 dB koherent RX-vinst snarare än 9. Det stämmer med att kanalerna skiljer sig mycket och snabbt (ofta >10 dB, ibland djupa nollställen), troligen på grund av sammansatt retur från reflektor och person.

**Om 994 m:** Den kurvan kom från en tidig ansats för Psi på 17 dBi per antennelement (ca 4 dB mer tvåvägsförstärkning än FARAD-IV) och Pfa = 1e-6, medan din 13 dB-tröskel motsvarar Pfa ≈ 2e-9. De går alltså inte att jämföra rakt av.

**Förslag till nästa mätning:** reflektor på stativ på några uppmätta avstånd och höjder, samma position med två chirp-lutningar, ett par TX-effektnivåer, och referenser utan reflektor och gärna med TX av. Det passar bra ihop med fasbrusmätningarna på gräsmattan, så det kan göras i samma session. Mät också reflektorns kantlängd: 10 dBsm vid 76 GHz motsvarar en triangulär trihedral med ca 7,8 cm inre kant från hörnet (ca 11 cm öppning).

Figur 1 (`reference_snr.png`): SNR per CPI, normerat till 100 m och 10 dBsm; streckad linje är modellen. Blått (väg ut) ingår inte i referensen.
Figur 2 (`pedestal_scaling.png`): brusplatån på reflektorns avstånd mot målets effekt (vänster) och mot effekt × (avstånd/30 m)² (mitten), där båda benen hamnar på samma kurva. Höger: platån relativt målets topp mot avstånd för benet in, som följer R² (20 dB/dekad).
