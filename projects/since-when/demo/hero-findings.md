# Hero findings: a shortlist a human can trust

Written by `check_quotes.py --write` from `hero-findings.json`; edit the JSON, not this file.

Every quote below is an exact substring of the plain text of the revision it names, as Wikipedia renders it at the permanent link (`python3 demo/check_quotes.py` prints pass or fail per quote; a finding with a failing quote is left out).
Each finding was reported by the product classifier (Nemotron, prompt version 6) and is in the scratch database; Haiku classified the same passage pairs as a second opinion.
The main list of a topic has only findings both models put in the same category. A finding the two models categorise differently, or a contradiction, is under "Needs a human look".
Where a statement says an edition does not mention something, the whole rendered article of that edition was searched by hand for it; the script checks the quotes, not the absence.
The tool links are to the walkthrough instance on the scratch database (pages and API on port 8078, see `HANDOFF.md`); the integrator checked each finding number against that instance by edition pair and quote. The finding number is the `id` in the API answer for the topic; after a restore of the snapshot the numbers may differ, and the finding is then found by its quote. How the list was made and what was left out: `hero-findings-notes.md`.

## Lapua Movement (Q1412941)

**1. The English and Swedish articles call the Lapua Movement "fascist" in their first sentence, while the Finnish first sentence calls it an anti-communist, radical-right popular movement and the Finnish introduction ends by saying that its leaders denied being fascists but that it fits almost every common definition of fascism. The word has come and gone: the English first sentence lost it on 7 June 2009, had it back on 30 May 2022 and gained "pro-Nazi" on 7 April 2026, and the Swedish first sentence gained it on 23 October 2026.**

- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “was a radical Finnish nationalist, fascist, pro-Nazi and anti-communist political movement founded in and named after the town of Lapua” (the first sentence today)
- sv, revision [59852897](https://sv.wikipedia.org/w/index.php?oldid=59852897) of 2026-11-11: “Lapporörelsen var en finländsk nationalistisk, fascistisk och antikommunistisk utomparlamentarisk politisk rörelse som grundades 1929 i Lappo” (the first sentence today)
- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “toiminut vaikutusvaltainen antikommunistinen ja oikeistoradikaali kansanliike” (the first sentence today: "an influential anti-communist and radical-right popular movement")
- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “Sen johtohahmot kielsivät olevansa fasisteja, mutta liikkeen aatteellinen tausta, tavoitteet ja toiminta täyttävät lähes kaikki yleisesti käytetyt fasismin määritelmät” (the last paragraph of the introduction today)
- en, revision [292260900](https://en.wikipedia.org/w/index.php?oldid=292260900) of 2009-05-25: “sometimes referred to as "Lapua Fascism", named after the then municipality and modern days town of Lapua, was a political movement in Finland” (the first sentence before the edit of 7 June 2009)
- en, revision [294882000](https://en.wikipedia.org/w/index.php?oldid=294882000) of 2009-06-07: “named after the then municipality and modern days town of Lapua, was a political movement in Finland” (the first sentence after that edit, without "Lapua Fascism")
- en, revision [1082481405](https://en.wikipedia.org/w/index.php?oldid=1082481405) of 2022-04-13: “was a radical Finnish nationalist and anti-communist political movement founded in and named after the town of Lapua” (the first sentence before the edit of 30 May 2022)
- en, revision [1090675024](https://en.wikipedia.org/w/index.php?oldid=1090675024) of 2022-05-30: “was a radical Finnish nationalist, fascist and anti-communist political movement founded in and named after the town of Lapua” (the edit that put the word back)
- en, revision [1129222214](https://en.wikipedia.org/w/index.php?oldid=1129222214) of 2022-12-24: “was a radical Finnish nationalist, fascist, pro-German and anti-communist political movement founded in and named after the town of Lapua” (24 December 2022)
- en, revision [1347550072](https://en.wikipedia.org/w/index.php?oldid=1347550072) of 2026-04-07: “was a radical Finnish nationalist, fascist, pro-Nazi and anti-communist political movement founded in and named after the town of Lapua” (the edit that changed "pro-German" to "pro-Nazi")
- sv, revision [59501859](https://sv.wikipedia.org/w/index.php?oldid=59501859) of 2026-07-21: “Lapporörelsen var en finländsk utomparlamentarisk och antikommunistisk rörelse som startades 1929” (the first sentence before the edit of 23 October 2026)
- sv, revision [59790252](https://sv.wikipedia.org/w/index.php?oldid=59790252) of 2026-10-23: “Lapporörelsen var en finländsk nationalistisk, fascistisk och antikommunistisk politisk rörelse som grundades 1929 i Lappo” (the edit that added the word)
- Category: Nemotron framing, Haiku framing
- In the tool: http://localhost:8078/#/Q1412941/en/fi/findings (finding 14044, English and Finnish; finding 14045 at http://localhost:8078/#/Q1412941/sv/fi/findings, Swedish and Finnish; both in http://localhost:8078/api/topics/Q1412941)
- The walkthrough's opening finding. The tool shows the same four dates on the walkthrough instance (`HANDOFF.md`); the dates here are from the revisions quoted.

**2. Swedish says 102 of the movement's leaders were imprisoned after the trial that followed the Mäntsälä rebellion; English says Wallenius and about 50 other leaders were sentenced to prison; Finnish says charges were brought against a hundred people and 22 were convicted of rebellion and 32 of aiding it.**

- sv, revision [59852897](https://sv.wikipedia.org/w/index.php?oldid=59852897) of 2026-11-11: “Efter den efterföljande rättegången, då 102 av rörelsens ledare fängslades, upplöstes Lapporörelsen”
- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “Wallenius and about 50 other leaders were sentenced to prison”
- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “Syytteet nostettiin sataa henkilöä vastaan. Turun hovioikeus tuomitsi marraskuussa yhteensä 22 henkilöä kapinasta ja 32 sen avunannosta” (not part of the classifier's finding, which compared Swedish with English)
- Category: Nemotron numbers, Haiku numbers
- In the tool: http://localhost:8078/#/Q1412941/sv/en/findings (finding 14096 in http://localhost:8078/api/topics/Q1412941)

**3. English says the movement was banned on 21 November 1932; Finnish says its activity was banned in practice on 29 February 1932, the organisation was dissolved on 24 March and a court confirmed that on 28 May; Swedish gives only the year.**

- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “After a trial, the Lapua Movement was banned on 21 November 1932 under the Protection of the Republic Act, which Lapua itself had worked to get passed”
- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “Lapuan Liike Ry:n toiminta kiellettiin käytännössä jo 29. helmikuuta tasavallan suojelulain nojalla. Apulaissisäministeri Arvo Manner lakkautti järjestön lopullisesti 24. maaliskuuta, ja raastuvanoikeus vahvisti päätöksen 28. toukokuuta”
- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “Lapuanliike kiellettiin ja lakkautettiin toukokuussa 1932” (the introduction)
- sv, revision [59852897](https://sv.wikipedia.org/w/index.php?oldid=59852897) of 2026-11-11: “Den upplöstes 1932 efter det misslyckade Mäntsäläupproret” (not part of the classifier's finding)
- Category: Nemotron numbers, Haiku numbers
- In the tool: http://localhost:8078/#/Q1412941/en/fi/findings (finding 13596 in http://localhost:8078/api/topics/Q1412941)

**4. Swedish puts the Peasant March to Helsinki on 7 July 1930 at about 12,000 men; English and Finnish put it at 12,600.**

- sv, revision [59852897](https://sv.wikipedia.org/w/index.php?oldid=59852897) of 2026-11-11: “Den 7 juli demonstrerade rörelsen sin styrka genom att samla omkring 12 000 utvalda män till ett bondetåg till Helsingfors”
- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “The Peasant March gathered 12,600 men to Helsinki”
- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “12 600 liikkeen kannattajaa marssi Helsinkiin” (not part of the classifier's finding)
- Category: Nemotron numbers, Haiku numbers
- In the tool: http://localhost:8078/#/Q1412941/sv/en/findings (finding 13531 in http://localhost:8078/api/topics/Q1412941)

**5. Finnish says the Peasant March was modelled on the Italian fascists' March on Rome of 1922; English describes the march without naming a model, and Swedish names Mussolini's Italy as the movement's model but not for the march.**

- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “Esikuva oli Italian fasistien mustapaitojen marssi Roomaan vuonna 1922, vaikka puhuttiin myös Ruotsin talonpoikien vuoden 1914 maanpuolustusmarssista”
- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “The Peasant March gathered 12,600 men to Helsinki where they marched through the city, held speeches and sermons and were greeted by distinguished politicians and generals” (the nearest English sentence)
- sv, revision [59852897](https://sv.wikipedia.org/w/index.php?oldid=59852897) of 2026-11-11: “Rörelsen inspirerades av fascistiska idéer, med Mussolinis Italien som förebild” (the nearest Swedish sentence)
- Category: Nemotron missing_fact, Haiku missing_fact
- In the tool: http://localhost:8078/#/Q1412941/en/fi/findings (finding 13980 in http://localhost:8078/api/topics/Q1412941)

**6. Finnish says election boards illegally struck up to 20,000 suspected communists from the electoral rolls before the 1930 election, with the help of the security police; English says such voters were removed and gives no number; Swedish does not mention it.**

- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “Eri puolilla Suomea vaalilautakunnat karsivat kuitenkin äänioikeutettujen listoilta laittomasti arvioiden mukaan jopa 20 000 kommunistiksi epäiltyä Etsivän Keskuspoliisin (EK) avustuksella”
- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “Voters perceived as communists were also outright removed from electoral rolls” (the nearest English sentence)
- Category: Nemotron missing_fact, Haiku missing_fact
- In the tool: http://localhost:8078/#/Q1412941/en/fi/findings (finding 13988 in http://localhost:8078/api/topics/Q1412941)

**7. English says many of the Finns the movement deported to the Soviet Union were later executed in Stalin's Great Purge; Swedish mentions the deportations but not what became of the deported, and Finnish does not mention the purge.**

- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “Many of the Finns deported by the Lapua Movement were later caught up in Stalin's Great Purge and executed”
- sv, revision [59852897](https://sv.wikipedia.org/w/index.php?oldid=59852897) of 2026-11-11: “Vissa oliktänkande fördes över gränsen till Sovjetunionen” (the nearest Swedish sentence)
- Category: Nemotron missing_fact, Haiku missing_fact
- In the tool: http://localhost:8078/#/Q1412941/sv/en/findings (finding 14087 in http://localhost:8078/api/topics/Q1412941)
- Haiku agrees for Swedish; for Finnish only Nemotron reported it (finding 13970).

**8. Finnish says the councils of about 70 municipalities were "cleansed" of communists before the new municipal law came into force; English and Swedish do not mention it.**

- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “Noin 70 kunnan kunnanvaltuustot ”puhdistettiin” kommunisteista jo ennen uuden kunnallislain voimaantuloa”
- Category: Nemotron missing_fact, Haiku missing_fact
- In the tool: http://localhost:8078/#/Q1412941/en/fi/findings (finding 14059 in http://localhost:8078/api/topics/Q1412941)

### Needs a human look

**1. After the wrecking of the Työn Ääni printing press, 72 men declared themselves responsible: English dates this to 4 April 1930, Finnish says they came to the governor in Vaasa on 9 April.**

- en, revision [1383067871](https://en.wikipedia.org/w/index.php?oldid=1383067871) of 2026-10-31: “On April 4th seventy-two men publicly declared themselves responsible for the attack, but only the actual perpetrators and the main organizer, Yrjö Nikula, were charged”
- fi, revision [24266018](https://fi.wikipedia.org/w/index.php?oldid=24266018) of 2026-09-24: “72 miestä, jotka saapuivat 9. huhtikuuta joukolla Vaasaan maaherran luo”
- Category: Nemotron numbers, Haiku contradiction
- In the tool: http://localhost:8078/#/Q1412941/en/fi/findings (finding 13953 in http://localhost:8078/api/topics/Q1412941)
- The two dates may be two steps of one event (a declaration, then the visit to the governor); someone who knows the sources should say.

## Finnish War (Q736268)

**1. Swedish says the siege of Sveaborg ended on 3 May 1808 with the capitulation; English says the fortress surrendered on 6 May 1808; Finnish says early May.**

- sv, revision [59682754](https://sv.wikipedia.org/w/index.php?oldid=59682754) of 2026-09-18: “Den ryska belägringen inleddes i medlet av mars 1808 och avslutades den 3 maj med Sveaborgs kapitulation”
- en, revision [1381826242](https://en.wikipedia.org/w/index.php?oldid=1381826242) of 2026-10-25: “The fortress surrendered on 6 May 1808”
- fi, revision [24241686](https://fi.wikipedia.org/w/index.php?oldid=24241686) of 2026-09-15: “Toukokuun 1808 alussa Viaporin piiritetty linnoitus antautui venäläisille” (not part of the classifier's finding, which compared Swedish with English)
- Category: Nemotron numbers, Haiku numbers
- In the tool: http://localhost:8078/#/Q736268/sv/en/findings (finding 14353 in http://localhost:8078/api/topics/Q736268)

**2. Swedish says almost 7,000 men were stationed at Sveaborg; English gives the fortress a garrison of 6,000 men.**

- sv, revision [59682754](https://sv.wikipedia.org/w/index.php?oldid=59682754) of 2026-09-18: “Nästan 7 000 man var förlagda till Sveaborg”
- en, revision [1381826242](https://en.wikipedia.org/w/index.php?oldid=1381826242) of 2026-10-25: “a garrison of 6,000 men”
- Category: Nemotron numbers, Haiku numbers
- In the tool: http://localhost:8078/#/Q736268/sv/en/findings (finding 14351 in http://localhost:8078/api/topics/Q736268)

**3. Finnish says the Savo Brigade had 3,500 men; Swedish calls it 4,000 strong.**

- fi, revision [24241686](https://fi.wikipedia.org/w/index.php?oldid=24241686) of 2026-09-15: “Savon prikaati koostui 3 500 miehestä, ja sitä oli vastassa 6 500 venäläistä sotilasta”
- sv, revision [59682754](https://sv.wikipedia.org/w/index.php?oldid=59682754) of 2026-09-18: “den 4 000 man starka Savolaxbrigaden, under Johan Adam Cronstedt, retirerade mot Uleåborg österifrån”
- Category: Nemotron numbers, Haiku numbers
- In the tool: http://localhost:8078/#/Q736268/sv/fi/findings (finding 14530 in http://localhost:8078/api/topics/Q736268)

### Needs a human look

**1. On the Russian advance over the ice towards Stockholm in March 1809: Swedish says von Döbeln averted the threat by negotiating the convention on Åland; English says the new king sent an embassy to Knorring proposing a truce, and the Russian commander agreed and recalled Kulnev.**

- sv, revision [59682754](https://sv.wikipedia.org/w/index.php?oldid=59682754) of 2026-09-18: “von Döbeln lyckades dock avvärja hotet mot huvudstaden genom att framförhandla konventionen på Åland”
- en, revision [1381826242](https://en.wikipedia.org/w/index.php?oldid=1381826242) of 2026-10-25: “the new king sent an embassy to Knorring, proposing a truce. The Russian commander agreed and speedily recalled Kulnev back to Åland”
- Category: Nemotron contradiction, Haiku contradiction
- In the tool: http://localhost:8078/#/Q736268/sv/en/findings (finding 14422 in http://localhost:8078/api/topics/Q736268)
- The two accounts credit different people and may both be true in part; someone who knows the sources should say.

## Diet of Porvoo (Q2457646)

**1. Finnish says the diet was convened on 22 March and closed on 19 July 1809; English says the estates were assembled between 25 March and 19 July; Swedish says the diet sat from 25 March to 18 July.**

- fi, revision [24273336](https://fi.wikipedia.org/w/index.php?oldid=24273336) of 2026-09-26: “Porvoon valtiopäivät oli kutsuttu koolle 22. maaliskuuta (J: 10. maaliskuuta), ja ne päätettiin 19. heinäkuuta (J: 7. heinäkuuta) 1809”
- en, revision [1384285215](https://en.wikipedia.org/w/index.php?oldid=1384285215) of 2026-11-07: “between 25 March and 19 July 1809”
- sv, revision [59835605](https://sv.wikipedia.org/w/index.php?oldid=59835605) of 2026-11-05: “Lantdagen sammanträdde 25 mars–18 juli 1809” (not part of the classifier's finding, which compared Finnish with English)
- Category: Nemotron numbers, Haiku numbers
- In the tool: http://localhost:8078/#/Q2457646/en/fi/findings (finding 14115 in http://localhost:8078/api/topics/Q2457646)

**2. Finnish says the name “valtiopäivät” is established, though some historians speak of “maapäivät”; Swedish calls “valtiopäivät” an anachronism for Porvoo, coined in 1847, and gives “Porvoon maapäivät” as the recommended Finnish term; English calls the name unhistorical in a footnote.**

- fi, revision [24273336](https://fi.wikipedia.org/w/index.php?oldid=24273336) of 2026-09-26: “Nimitys ”valtiopäivät” on vakiintunut, mutta jotkut historiantutkijat puhuvat ”maapäivistä”, joka on suora käännös ruotsinkielisestä nimestä ”Borgå lantdag””
- sv, revision [59835605](https://sv.wikipedia.org/w/index.php?oldid=59835605) of 2026-11-05: “Eftersom ordet valtio inte fanns i finskan år 1809 kan valtiopäivät betraktas som anakronistiskt i fråga om Borgå, och som rekommenderad finsk term anges i stället Porvoon maapäivät, som återger den samtida svenska benämningen”
- sv, revision [59835605](https://sv.wikipedia.org/w/index.php?oldid=59835605) of 2026-11-05: “Ordet valtiopäivät ("statens dagar") myntades 1847 av fennomanen Paavo Tikkanen, som tillämpade det just på mötet i Borgå” (the classifier's missing-fact finding on the same pair of passages; Finnish names neither Tikkanen nor 1847)
- en, revision [1384285215](https://en.wikipedia.org/w/index.php?oldid=1384285215) of 2026-11-07: “The Finnish word for a Diet, valtiopäivät, was invented only in the mid-19th century and so calling the lantdag in Porvoo that name is unhistorical” (not part of the classifier's finding, which compared Finnish with Swedish)
- Category: Nemotron framing, Haiku framing
- In the tool: http://localhost:8078/#/Q2457646/sv/fi/findings (finding 14182 in http://localhost:8078/api/topics/Q2457646)

**3. Swedish reports a learned debate of 1838–1843 in which Israel Hwasser held that the diet had been a regular treaty between Russia and Finland and Adolf Ivar Arwidsson objected; English and Finnish mention neither man.**

- sv, revision [59835605](https://sv.wikipedia.org/w/index.php?oldid=59835605) of 2026-11-05: “Redan i en lärd debatt 1838–1843 hävdade Israel Hwasser att lantdagen varit ett regelrätt statsfördrag mellan Ryssland och Finland, medan Adolf Ivar Arwidsson invände mot tolkningen”
- Category: Nemotron missing_fact, Haiku missing_fact
- In the tool: http://localhost:8078/#/Q2457646/en/sv/findings (finding 14191 in http://localhost:8078/api/topics/Q2457646)

### Needs a human look

**1. Finnish says Finland's military establishment stayed as it was; Swedish says conscription was suspended for fifty years and replaced by vacancy fees.**

- fi, revision [24273336](https://fi.wikipedia.org/w/index.php?oldid=24273336) of 2026-09-26: “Suomen sotalaitos pysyi entisellään”
- sv, revision [59835605](https://sv.wikipedia.org/w/index.php?oldid=59835605) of 2026-11-05: “värnplikten, som inställdes för femtio år och ersattes med vakansavgifter”
- Category: Nemotron contradiction, Haiku contradiction
- In the tool: http://localhost:8078/#/Q2457646/sv/fi/findings (finding 14175 in http://localhost:8078/api/topics/Q2457646)
- The two may describe the same decision from two sides (the allotment system kept on paper, its troops not raised); someone who knows the sources should say.
