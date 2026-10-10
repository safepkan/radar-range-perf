**CARKIT-valideringen är klar.** Rapporten (bifogad, 7 sidor) sammanfattar vad mätningarna säger om vår räckviddsmodell och om LO:ns fasbrus, och vad det betyder för Lannik Psi. Den citerar Infineons NDA-datablad, så den stannar internt. Stort tack till Viktor för alla mätningar!

Kort version:
• **Modellen håller inom ca 1 dB.** Med en referensreflektor på fast montage i mätkammaren hamnar CARKIT 0.4–0.7 dB under modellen med databladets typvärden. Ingen empirisk korrektion behövs.
• **Reflektorns riktning avgör.** En hörnreflektor tappar 3–11 dB när den pekar 20–30° snett, så burna reflektorer duger inte som absolut referens. Troligen förklarar det de låga nivåerna i fältmätningarna, med reflektorn både på stativ och buren.
• **Tiden mellan chirparna är en designparameter.** Med 15–25 µs flyback och väntan mellan chirparna ligger frekvensfelet per chirp på den nivå databladets fasbrus ger, och kostar ca 0.1 dB vid 1 km. Infineons firmware lämnade nästan ingen tid, vilket gav 4–9 gånger större fel. Det hade kostat 1.5–7 dB vid 1 km.
• **Starka ekon nära radarn höjer brusgolvet på alla avstånd** genom LO:ns fasbrus. I mätkammaren begränsar det vad koherent kanalsummering ger, så den vinsten säger inget om räckvidd.
• **För Psi:** RX-förstärkning +3 dB, chirp-timing med marginal, en egen mätning av radomen, och hantering av interferens från andra radarer nära trafik.

En rättelse till mitt inlägg 29/9: det höga frekvensfelet per chirp, 8–12 dB över databladet, gällde bara Infineons chirp-timing. Med vår ligger det på databladets nivå.
