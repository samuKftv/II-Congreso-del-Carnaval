# Prompts optimizados para FLUX.2 Klein · CarnaLab 2026

El botón **🎲 Inspírame** del móvil propone una de estas ideas en español. Si la persona la usa **tal cual**, el
estudio manda a FLUX.2 su prompt optimizado en inglés (sin intérprete ni receta encima). Si la cambia, pasa por
el intérprete y lleva la ambientación de carnaval, como cualquier otra idea.

Están en `config/estilos.json`, en `"ideas"`: cada una con `"idea"` (lo que ve la gente) y `"prompt"` (lo que
recibe FLUX.2). Puedes cambiarlas o añadir más con el Bloc de notas; una idea sin `"prompt"` pasa por el intérprete.
Para ver cómo quedan con tu modelo, ejecuta `5-PROBAR-MI-MODELO.bat`: prueba las cuatro primeras.

**¿Z-Image Turbo o FLUX.2 Klein?** Ejecuta `5-PROBAR-MI-MODELO.bat` dos veces y compara las dos hojas:
una con `[mi_modelo]` vacío (`base = "z-image-turbo"`) y otra con `base = "flux2-klein-4b"` y tu modelo y tu
LoRA. Salen las mismas ideas con sus prompts optimizados y los segundos por imagen de cada uno.

## Cómo están escritos (guía de Black Forest Labs para FLUX.2)

1. **Sujeto + acción + estilo + contexto.** Quién o qué, qué hace, cómo se ve (tipo de foto o ilustración)
   y dónde, con qué luz y ambiente.
2. **Lo importante, primero.** FLUX.2 presta más atención al principio del prompt: primero el sujeto y lo
   que hace, después los detalles del traje y al final el lugar, la luz y el ambiente.
3. **Frases, no listas de palabras.** "Una reina posando en un escenario con un traje de plumas" funciona
   mejor que "reina, plumas, escenario, 8k, obra maestra".
4. **Sin negativos.** FLUX.2 no usa prompt negativo: se describe lo que tiene que salir, nunca lo que no.
5. **Longitud media para la mayoría de escenas.** Los prompts cortos sirven para probar rápido; los muy
   largos, solo para escenas con muchos personajes o detalles técnicos.

Y dos criterios nuestros para el congreso:

6. **Decir siempre la luz y el tipo de foto** (foco de escenario, luz de ventana, farolillos, atardecer;
   foto de calle, de gala, retrato, vista aérea): así todas las imágenes del mosaico tienen calidad pareja.
   Aquí van de 30 a 65 palabras.
7. **Siempre el carnaval de Santa Cruz de Tenerife**, con materiales concretos: lentejuelas, plumas,
   pedrería, raso, purpurina, confeti, serpentinas.

Las ideas que escribe la gente siguen las mismas reglas: el intérprete las reescribe así y luego se les añade
la ambientación de carnaval (estilo `carnaval`):

> {prompt}. Vibrant editorial photography at the Carnival of Santa Cruz de Tenerife: spectacular costumes with sequins, feathers and rhinestones, confetti and colorful streamers in the air, festive lights, rich saturated colors, sharp detail.

## Las ideas

1. **La Reina del Carnaval con un traje gigante inspirado en el Teide**  
   The Carnival Queen of Santa Cruz de Tenerife posing proudly in a monumental costume inspired by the Teide volcano: a gigantic backpiece shaped like the mountain, red and orange sequins flowing like lava, black rhinestones like volcanic rock and white feathers like snow on the summit. Spectacular gala photography on a huge stage, dramatic spotlights, sparkling reflections, wide shot, rich saturated colors.

2. **Una murga de pulpos cantando en el escenario del carnaval**  
   A murga of six cheerful purple octopuses in identical red and yellow satin costumes with ruffled collars and painted clown faces, singing and blowing kazoos with their tentacles on the open-air carnival stage of Santa Cruz de Tenerife. Vibrant event photography, colorful spotlights, confetti falling, a crowd in costumes cheering in the background, sharp detail.

3. **Una murga de Santa Cruz cantando en la calle con trajes de colores**  
   A murga of twenty singers in identical patchwork costumes of yellow, green and red satin with huge ruffled collars and painted faces, singing funny songs with kazoos and drums in a crowded street of Santa Cruz de Tenerife. Lively street photography, warm evening light, confetti and serpentine streamers in the air, joyful faces, vivid colors.

4. **Una comparsa bailando samba en el Coso con plumas de colores**  
   A comparsa of smiling dancers in sequined costumes and enormous headdresses of turquoise, gold and fuchsia feathers dancing samba down the main avenue during the Coso parade of Santa Cruz de Tenerife, drummers behind them. Sunny daytime street photography, motion and energy, confetti in the air, cheering crowd on both sides, vivid colors.

5. **Una diseñadora cosiendo un traje de plumas enorme en su taller**  
   A carnival costume designer stitching rhinestones onto an enormous costume of white and golden feathers on a mannequin in her workshop, surrounded by rolls of shiny fabric, sketches pinned to the wall and boxes of sequins. Warm documentary photography, soft window light, sparkles catching the light, shallow depth of field.

6. **Un maquillador transformando a una murguera en un pavo real**  
   A makeup artist painting the face of a smiling murga singer, turning her into a peacock with blue, green and gold face paint, glitter and tiny rhinestones around her eyes, backstage at the carnival of Santa Cruz de Tenerife. Close-up beauty photography, bright mirror lights, vivid colors, fine detail on the brushes and sparkles.

7. **Unos artesanos construyendo una carroza gigante con forma de pez**  
   Artisans building a gigantic parade float shaped like a smiling tropical fish, painting its scales in turquoise and coral and gluing hundreds of small mirrors onto it inside a huge warehouse, scaffolding and paint buckets around them. Wide documentary photography, warm work lights, dust in the air, strong sense of scale.

8. **El Entierro de la Sardina con viudas llorando muy exageradas**  
   The Burial of the Sardine at the Carnival of Santa Cruz de Tenerife: a giant papier-mache sardine carried through the street at night, followed by a crowd of men dressed as mourning widows in black lace veils, crying dramatically and laughing at the same time. Night street photography, torches and warm streetlights, humorous festive mood.

9. **Un perro disfrazado de mascarita en el carnaval de día**  
   A happy golden retriever wearing a carnival costume with a sequined cape, a tiny top hat and a feathered mask, trotting among people in costumes at the daytime street carnival of Santa Cruz de Tenerife. Bright sunny street photography, confetti on the ground, streamers hanging between the buildings, cheerful mood, sharp focus on the dog.

10. **Una rondalla tocando timples y guitarras bajo la luna**  
   A rondalla of singers in elegant matching costumes of black velvet with silver embroidery playing timples, guitars and lutes under a full moon on a plaza of Santa Cruz de Tenerife decorated with paper lanterns. Atmospheric night photography, warm lantern light against a deep blue sky, romantic and festive mood.

11. **Una guagua convertida en carroza de carnaval**  
   A classic yellow and blue Canarian bus transformed into a carnival float, covered in giant paper flowers, mirrors and feathers, with a salsa band playing on its roof and dancers in sequined costumes waving from the windows as it drives through Santa Cruz de Tenerife. Sunny street photography, cheering crowds, vivid colors.

12. **El drago milenario disfrazado para el carnaval**  
   The ancient dragon tree of Icod de los Vinos dressed up for carnival, its branches decorated with colorful streamers, giant paper flowers and lanterns and a huge sequined mask on its trunk, people in costumes dancing around it. Magical evening photography, warm string lights, sunset sky, festive and whimsical mood.

13. **Una niña disfrazada de plátano canario bailando en el coso infantil**  
   A smiling little girl in a funny Canarian banana costume with a bright yellow peel and tiny green leaves on her head, dancing with joy in the children's carnival parade of Santa Cruz de Tenerife, confetti in the air. Bright daytime photography, other children in colorful costumes around her, happy and playful mood.

14. **Un traje de fantasía hecho de espejos y luces de neón**  
   A performer wearing a breathtaking fantasy costume made of thousands of tiny mirrors and glowing neon tubes in pink and electric blue, with a towering headdress, posing on a dark carnival stage. Dramatic stage photography, beams of light reflecting in every direction, haze, high contrast, mesmerizing atmosphere.

15. **Un murguero tocando el bombo con la cara pintada**  
   Close-up portrait of a murga drummer with his face painted half yellow and half red, glitter on his cheeks and a tall hat with ribbons, playing a big bass drum with passion on the carnival stage of Santa Cruz de Tenerife. Dramatic portrait photography, colored spotlight from the side, sparkles, shallow depth of field.

16. **Una costurera bordando lentejuelas a mano**  
   Close-up of a seamstress's hands embroidering tiny sequins one by one onto a shimmering turquoise carnival costume, the needle and thread catching the light, spools of colored thread and boxes of beads around her. Macro photography, warm lamp light, glittering bokeh, extremely fine detail.

17. **Un iluminador preparando las luces del escenario de la gala de la Reina**  
   A lighting technician on a tall rig adjusting colorful spotlights above the huge stage of the Carnival Queen gala in Santa Cruz de Tenerife, beams of magenta and cyan light cutting through the haze, the glittering empty stage below. Cinematic backstage photography, dramatic atmosphere, strong sense of scale.

18. **Una abuela y su nieta con el mismo disfraz**  
   A grandmother and her granddaughter wearing identical carnival costumes of pink feathers and golden sequins, laughing and dancing together in the street during the daytime carnival of Santa Cruz de Tenerife. Warm candid photography, sunny light, confetti and streamers around them, joyful and tender mood.

19. **Un gato con antifaz y capa de lentejuelas mirando los fuegos artificiales**  
   A fluffy black cat wearing a tiny golden eye mask and a sequined purple cape, sitting on a rooftop above the carnival of Santa Cruz de Tenerife at night, fireworks bursting in the sky and the colorful lit streets below. Cinematic night photography, glowing fireworks, magical mood, sharp detail on the cat.

20. **Fuegos artificiales sobre el carnaval de Santa Cruz**  
   Spectacular fireworks exploding in gold, red and turquoise over the port of Santa Cruz de Tenerife during carnival, thousands of people in costumes dancing on the avenue below, the illuminated city along the sea. Wide night photography, long exposure light trails, reflections on the water, festive atmosphere.

21. **Un pulpo gigante disfrazado de pirata en la cabalgata**  
   A giant cheerful octopus dressed as a pirate captain with a tricorn hat covered in gold sequins and a feathered cape, waving its tentacles from a ship-shaped float in the carnival parade of Santa Cruz de Tenerife, confetti and streamers flying. Playful vibrant photography, sunny day, cheering crowd, saturated colors.

22. **Un zapatero haciendo unas plataformas gigantes con purpurina**  
   A shoemaker in his workshop crafting enormous glittering platform boots for a carnival costume, covered in red rhinestones and silver glitter, tools and pieces of leather on the wooden workbench. Warm documentary photography, golden lamp light, sparkling highlights, detailed textures.

23. **Una peluquera creando un peinado imposible para el carnaval**  
   A hairdresser backstage at the carnival of Santa Cruz de Tenerife creating an impossible sculptural hairstyle in electric pink and turquoise, decorated with feathers, pearls and tiny mirrors, for a smiling woman in a sequined costume. Beauty photography, bright vanity mirror lights, vivid colors, fine detail.

24. **El carnaval de Santa Cruz visto desde el cielo**  
   Aerial view of the Carnival of Santa Cruz de Tenerife at night: a river of people in colorful costumes filling the avenues, illuminated floats and stages, clouds of confetti, the port and the dark ocean beside the city. Drone photography, glowing city lights, vibrant festive colors, strong sense of scale.

25. **Un robot disfrazado de mascarita bailando salsa**  
   A friendly retro robot wearing a carnival costume with a feathered headdress, a sequined bow tie and a colorful mask, dancing salsa with people in costumes in a street of Santa Cruz de Tenerife at night. Playful vibrant photography, neon signs and string lights, confetti, joyful mood.

26. **Una pareja de mayores ganando el concurso de disfraces**  
   An elderly couple in matching handmade costumes of the sun and the moon, covered in golden and silver sequins, holding a trophy and laughing on the stage of a carnival costume contest in Santa Cruz de Tenerife. Warm event photography, spotlights, confetti falling, emotional and festive mood.

27. **Una banda tocando trompetas entre una lluvia de confeti**  
   A carnival brass band in shiny turquoise uniforms with golden epaulettes playing trumpets and trombones in a street of Santa Cruz de Tenerife, a storm of colorful confetti falling around them. Energetic street photography, bright sunlight, gleaming brass, vivid colors.

28. **Un traje de carnaval hecho con materiales reciclados**  
   A proud designer presenting a spectacular carnival costume made entirely of recycled materials: a giant backpiece of colorful plastic bottle caps, old CDs that shine like mirrors and feathers cut from plastic bags, on a carnival stage. Editorial photography, bright spotlights, sparkling reflections, inspiring mood.

29. **Una máscara de carnaval dorada con plumas de colores**  
   A golden carnival mask decorated with filigree, rhinestones and colorful peacock feathers resting on a red velvet cushion, confetti scattered around it. Luxury still life photography, dark background, soft spotlight, sparkling highlights, sharp detail.

30. **Un arlequín veneciano en una góndola llena de confeti**  
   A Venetian harlequin in a diamond-patterned costume of red, gold and black and a white porcelain mask, standing in a gondola full of confetti as it glides along a canal in Venice during carnival. Elegant photography at golden hour, soft mist over the water, ornate palaces in the background, warm rich colors.

31. **Una bailarina de Río con un tocado de plumas del tamaño de un árbol**  
   A Rio de Janeiro samba dancer wearing a golden feather headdress as big as a tree and a costume covered in crystals, dancing on top of a colossal float in the Sambadrome at night, thousands of spectators behind her. Spectacular event photography, blazing stage lights, motion and glitter, intense colors.

32. **Un astronauta celebrando el carnaval en la Luna**  
   An astronaut in a white spacesuit decorated with sequins, feathers and colorful streamers dancing on the surface of the Moon, a small carnival float and confetti floating in low gravity, the Earth shining in the black sky. Cinematic science fiction photography, sharp sunlight, glittering details, playful mood.
