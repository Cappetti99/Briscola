"""Italian presentation catalogue; game state and persisted identifiers stay stable."""
import re
import tkinter as tk

IT = {
'Resume game': 'Riprendi partita', 'Hint': 'Consiglio', 'Review': 'Rivedi mosse',
'Settings': 'Impostazioni', 'Language': 'Lingua', 'Animation speed': 'Velocità animazioni',
'Cards': 'Carte', 'Save': 'Salva', 'Slow': 'Lenta', 'Normal': 'Normale', 'Fast': 'Rapida',
'French suits': 'Semi francesi', 'Italian suits': 'Semi italiani',
'No saved game is available.': 'Non ci sono partite da riprendere.',
'The saved game cannot be read.': 'Impossibile leggere la partita salvata.',
'Wait for your turn to request a hint.': 'Attendi il tuo turno per chiedere un consiglio.',
'No completed moves to review yet.': 'Non ci sono ancora mosse da rivedere.',
'Training game: this match will not affect your statistics.': 'Allenamento: questa partita non modifica le statistiche.',
'This wins the current trick while limiting the card value spent.': 'Questa carta vince la presa limitando il valore delle carte impiegate.',
'Keep valuable cards and trumps for more profitable tricks.': 'Conserva i carichi e le briscole per prese più vantaggiose.',
'This card stays on the table.': 'Questa carta resta sul tavolo.',
'The suggestion weighs coins, settebello, primiera and the risk of a scopa.': 'Il consiglio valuta denari, settebello, primiera e il rischio di lasciare una scopa.',
'Respect the lead suit, preserve valuable cards and favour control of the suit.': 'Rispetta il seme di uscita, conserva le carte di valore e cerca il controllo del seme.',
'Take the discard pile.': 'Raccogli il monte scarti.',
'The visible cards improve your possible melds enough to justify the cost.': 'Le carte visibili migliorano le combinazioni possibili abbastanza da giustificare il costo.',
'Draw a card from the stock.': 'Pesca una carta dal mazzo.',
'The visible discard pile does not sufficiently improve your melds.': 'Il monte scarti visibile non migliora abbastanza le tue combinazioni.',
'Recover the wild card for another meld.': 'Recupera la matta per un’altra combinazione.',
'Move these cards onto the table to reduce your hand penalty.': 'Cala queste carte per ridurre i punti rimasti in mano.',
'Grow the meld towards a burraco.': 'Allunga la combinazione per avvicinarti al burraco.',
'Keep cards that are more useful for building or extending melds.': 'Conserva le carte più utili per creare o allungare le combinazioni.',
'Start game': 'Inizia partita', 'Statistics': 'Statistiche', 'Rules': 'Regole',
'Close': 'Chiudi', 'Menu': 'Menu', 'menu': 'menu', 'change': 'cambia',
'New game': 'Nuova partita', 'New match': 'Nuova partita', 'Next hand': 'Mano successiva',
'one hand': 'una mano', 'DIFFICULTY': 'DIFFICOLTÀ', 'GAME': 'GIOCO',
'PLAY UP TO': 'PUNTEGGIO OBIETTIVO', 'PLAYER': 'GIOCATORE',
'YOU': 'TU', 'COMPUTER': 'COMPUTER', 'you vs. the computer': 'tu contro il computer',
'Easy': 'Facile', 'Expert': 'Esperto', 'TRUMP': 'BRISCOLA', 'TRUMP SUIT': 'SEME DI BRISCOLA',
'LAST TRICKS': 'ULTIME PRESE', 'LAST MOVES': 'ULTIME MOSSE', 'led': 'uscita',
'no melds yet': 'nessuna combinazione', 'the table is empty': 'il tavolo è vuoto',
'Enter = start    D = difficulty    S = statistics    R = rules': 'Invio = inizia    D = difficoltà    S = statistiche    R = regole',
'Trick taking with 40 cards. Short, sharp, first to 61.': '40 carte, una briscola. Vince chi arriva a 61.',
'Melds, wild cards and the pot. Longer, and more to think about.': 'Combinazioni, pinelle e pozzetto. Una sfida di strategia.',
'Match cards off the table. Quick, and all about what you leave.': 'Prendi le carte e fai attenzione a ciò che lasci.',
'No trumps, and you must follow suit. Ten cards, and counting.': 'Devi rispondere al seme. Dieci carte, nessuna briscola.',
'Plays almost at random. A gentle start.': 'Gioca quasi a caso. Per iniziare senza fretta.',
'Solid classic play: it ducks and saves its trumps.': 'Gioco classico: cede le prese e conserva le briscole.',
'Counts cards and searches ahead. Hard to beat.': 'Conta le carte e analizza le mosse future.',
'Melds whatever it can, and throws away at random.': 'Cala ciò che può e scarta a caso.',
'Builds towards burracos and weighs up taking the pile.': 'Costruisce burraco e valuta il monte scarti.',
'Takes whatever it happens to pick. A gentle start.': 'Sceglie le prese a caso. Per iniziare.',
'Takes the valuable cards and avoids handing you a scopa.': 'Prende le carte di valore e cerca di evitare le scope.',
'Deals out the cards it cannot see and plays them out.': 'Simula possibili distribuzioni delle carte sconosciute.',
'Plays any card the rules allow. A gentle start.': 'Sceglie a caso fra le carte consentite.',
'Knows which card commands a suit, and spends nothing.': 'Valuta il controllo dei semi e conserva i punti.',
'Your turn: lead a card.': 'Tocca a te: gioca una carta.',
'Your turn: draw a card, or take the pile.': 'Tocca a te: pesca o raccogli gli scarti.',
'Draw': 'Pareggio', 'You win!': 'Hai vinto!', 'You lose': 'Hai perso',
'You win the match!': 'Hai vinto la partita!', 'You lose the match': 'Hai perso la partita',
'Hand over': 'Mano terminata', 'Player': 'Giocatore', 'Player name:': 'Nome del giocatore:',
'Draw a card': 'Pesca una carta', 'Take the pile': 'Raccogli scarti', 'Lay down': 'Cala',
'Discard': 'Scarta', 'Sort by suit': 'Ordina per seme', 'Sort by rank': 'Ordina per valore',
'Hide my hand': 'Nascondi mano', 'Show my hand': 'Mostra mano',
'Take the pinella': 'Recupera pinella', 'Clear the picks': 'Annulla selezione',
'Select exactly one card to discard.': 'Seleziona una sola carta da scartare.',
'Select the one card the pinella is standing in for.': 'Seleziona la carta rappresentata dalla pinella.',
'Pick cards that add up to it exactly.': 'Seleziona carte la cui somma corrisponde al valore giocato.',
'It takes nothing, so it stays on the table.': 'Non prende niente, quindi resta sul tavolo.',
'A card of the same value is on the table, and that one has to be taken.': 'Devi prendere la carta dello stesso valore presente sul tavolo.',
'STATISTICS': 'STATISTICHE', 'Played': 'Giocate', 'Won': 'Vinte', 'Lost': 'Perse',
'Win rate': '% vittorie', 'Avg points': 'Media punti', 'Best score': 'Record',
'RECENT MATCHES': 'PARTITE RECENTI', 'date': 'data', 'result': 'esito',
'score': 'punti', 'difficulty': 'difficoltà', 'opened': 'inizio',
'No games recorded yet.': 'Nessuna partita registrata.', 'Records are saved to:': 'Risultati salvati in:',
'All games': 'Tutti i giochi', 'All levels': 'Tutte le difficoltà',
'WIN': 'VINTA', 'LOSS': 'PERSA', 'DRAW': 'PARI', 'no games yet': 'nessuna partita',
'You': 'Tu', 'you': 'tu', 'The computer': 'Il computer', 'the computer': 'il computer',
'computer': 'computer', 'stock': 'mazzo', 'empty': 'vuoto', 'points': 'punti',
'Cards left': 'Carte rimaste', 'Coins': 'Denari', 'Primiera': 'Primiera',
}

# Ordered, full-string templates preserve interpolated values instead of translating
# arbitrary substrings (which could damage player names or filesystem paths).
TEMPLATES = [
(r'Play (.+)\.', 'Gioca {0}.'),
(r'Capture these table cards: (.+)', 'Prendi queste carte dal tavolo: {0}'),
(r'Replace the wild card with (.+)\.', 'Sostituisci la matta con {0}.'),
(r'Lay down: (.+)', 'Cala: {0}'), (r'Add (.+) to meld (\d+)\.', 'Aggiungi {0} alla combinazione {1}.'),
(r'Discard (.+)\.', 'Scarta {0}.'),
(r'Rules of (.+)', 'Regole di {0}'), (r'Difficulty: (.+)', 'Difficoltà: {0}'),
(r'The computer led (.+)\. Your answer\?', 'Il computer ha giocato {0}. Come rispondi?'),
(r'The computer (?:leads|answers with) (.+)\.', 'Il computer gioca {0}.'),
(r'You play (.+)\.', 'Giochi {0}.'),
(r'(You take|The computer takes|You takes) the trick: \+(\d+) (points|thirds)(.*)\.', '{0} la presa: +{1} {2}{3}.'),
(r'New game\. Trump: (.+)\. (you lead|the computer leads)\.', 'Nuova partita. Briscola: {0}. {1}.'),
(r'New hand of Scopa: (you start|the computer starts)\.', 'Nuova mano di Scopa: {0}.'),
(r'New hand of Burraco\. (you start|the computer starts): draw a card, or take the discard pile\.', 'Nuova mano di Burraco: {0}. Pesca o raccogli gli scarti.'),
(r'Current streak: (.+)', 'Serie attuale: {0}'),
(r'Best winning streak: (\d+)', 'Migliore serie di vittorie: {0}'),
(r'Wins by difficulty: (.+)', 'Vittorie per difficoltà: {0}'),
(r'(\d+) win(?:s)? in a row', '{0} vittorie consecutive'),
(r'(\d+) loss(?:es)? in a row', '{0} sconfitte consecutive'),
(r'(\d+) played - (\d+)W (\d+)L (\d+)D  \((\d+)% won\)', '{0} giocate · {1} vinte · {2} perse · {3} pari ({4}%)'),
(r'You win (\d+) to (\d+)\.', 'Hai vinto {0} a {1}.'),
(r'The computer wins (\d+) to (\d+)\.', 'Il computer vince {0} a {1}.'),
(r'Draw, (\d+) to (\d+)\.', 'Pareggio, {0} a {1}.'),
(r'(.+) cards', '{0} carte'), (r'(.+) points', '{0} punti'),
(r'Computer draws .+', 'Il computer pesca una carta'),
(r'Computer discards (.+)', 'Il computer scarta {0}'),
(r'You discard (.+)', 'Scarti {0}'),
(r'(.+) / (.+)', '{0} / {1}'),
]
IT.update({'You take': 'Prendi', 'You takes': 'Prendi', 'The computer takes': 'Il computer prende',
           'thirds': 'terzi', ' - the last trick': ' - ultima presa',
           'you lead': 'inizi tu', 'the computer leads': 'inizia il computer',
           'you start': 'inizi tu', 'the computer starts': 'inizia il computer'})
SUITS = {'Diamonds': 'quadri', 'Hearts': 'cuori', 'Spades': 'picche', 'Clubs': 'fiori'}
ITALIAN_SUITS = {'Diamonds': 'denari', 'Hearts': 'coppe', 'Spades': 'spade', 'Clubs': 'bastoni'}
RANKS = dict(zip(('Ace Two Three Four Five Six Seven Eight Nine Ten Jack Queen King').split(),
                ('Asso Due Tre Quattro Cinque Sei Sette Otto Nove Dieci Fante Donna Re').split()))

RULES_IT = {
'briscola': '''Si gioca con 40 carte. Si distribuiscono tre carte a testa; la carta
scoperta sotto il mazzo indica il seme di briscola.

Valori: asso 11, tre 10, re 4, donna/cavallo 3, fante 2.
Forza: A > 3 > K > Q > J > 7 > 6 > 5 > 4 > 2.
Non è obbligatorio rispondere al seme. Vince la carta più forte
del seme di uscita, oppure una briscola contro un altro seme.
Chi prende pesca per primo e apre la presa successiva.
La briscola scoperta viene pescata per ultima.

Ci sono 120 punti: vince chi ne totalizza almeno 61; 60–60 è pari.
Comandi: clic su una carta oppure 1, 2, 3. Spazio salta la pausa.''',
'scopa': '''Si gioca con 40 carte: quattro sul tavolo e tre a ciascun giocatore.
Terminate le carte in mano, se ne distribuiscono altre tre.

La carta giocata prende una carta dello stesso valore. Solo in
assenza di una carta uguale puoi prendere più carte la cui somma
corrisponde al valore giocato. Le figure valgono 8, 9 e 10.
Se non prende, la carta resta sul tavolo. Svuotare il tavolo vale
una scopa, tranne con l'ultima carta della mano.
Chi ha preso per ultimo raccoglie le carte rimaste sul tavolo.

Un punto per: più carte, più denari, settebello e migliore primiera.
Le parità non assegnano punti. Ogni scopa vale un punto.
Primiera: 7=21, 6=18, A=16, 5=15, 4=14, 3=13, 2=12, figure=10.
Si somma la migliore carta di ciascun seme.

Clic o tasti 1–3 per giocare. Se ci sono più prese possibili,
seleziona prima le carte sul tavolo. Vince chi raggiunge
l'obiettivo con un vantaggio; in parità si continua.''',
'burraco': '''Due mazzi da 54 carte, undici carte a testa e due pozzetti da undici.
Pesca una carta oppure raccogli tutto il monte scarti; puoi poi
calare e allungare combinazioni. Termina scartando una carta.

Le combinazioni sono gruppi dello stesso valore o scale dello
stesso seme di almeno tre carte. L'asso può essere basso o alto.
Jolly e due sono matte: al massimo una per combinazione;
il due del seme della scala può avere il proprio valore naturale.
Sette carte formano un burraco: pulito 200, con matta 100 punti.

Finire la mano per la prima volta dà il pozzetto. Per chiudere
dopo il pozzetto serve almeno un burraco. Chiusura: +100.
Carte calate positive, carte in mano negative: jolly 30,
due 20, asso 15, da 8 a re 10, da 3 a 7 cinque punti.
Pozzetto non preso o non giocato: penalità di 100 punti.

Seleziona le carte, poi Cala, Scarta o clicca una combinazione
per allungarla. Recupera pinella sostituisce una matta con la
carta naturale. Vince chi raggiunge l'obiettivo in vantaggio.''',
 'tressette': '''40 carte, dieci a testa e venti nel mazzo. Nessuna briscola.
Forza: 3 > 2 > A > K > Q > J > 7 > 6 > 5 > 4.
È obbligatorio rispondere al seme: le carte non consentite
sono attenuate. Vince la più forte del seme di uscita.
Chi prende pesca per primo e apre. Le pescate sono scoperte.

Punti in terzi: asso 3, due/tre/figure 1, altre carte 0.
L'ultima presa vale altri 3 terzi. Ogni giocatore divide i propri
terzi per tre, scartando il resto.

Accuse nella mano iniziale: asso, due e tre dello stesso seme
formano una napoletana da 3 punti. Tre assi, due o tre valgono
3 punti; quattro dello stesso valore ne valgono 4.

Clic o tasti 1–9 e 0 per la decima carta. Vince chi raggiunge
l'obiettivo in vantaggio; in caso di parità si continua.'''}


def translate(text, language='en', italian_suits=False):
    if not isinstance(text, str):
        return text
    if language != 'it':
        if italian_suits:
            for old, new in {'Diamonds': 'Coins', 'Hearts': 'Cups', 'Spades': 'Swords', 'Clubs': 'Batons', 'Queen': 'Knight'}.items():
                text = re.sub(r'\b' + old + r'\b', new, text)
        return text
    if text in IT:
        return IT[text]
    suits = ITALIAN_SUITS if italian_suits else SUITS
    if text in suits:
        return suits[text]
    short = re.fullmatch(r'([A2-9JQK]|10)/(di|he|sp|cl)', text)
    if short:
        rank = {'J': 'F', 'Q': 'C', 'K': 'R'}.get(short[1], short[1]) if italian_suits else short[1]
        suffixes = {'di': 'de', 'he': 'co', 'sp': 'sp', 'cl': 'ba'} if italian_suits else {'di': 'qu', 'he': 'cu', 'sp': 'pi', 'cl': 'fi'}
        return rank + '/' + suffixes[short[2]]
    if '\n' in text:
        return '\n'.join(translate(line, language, italian_suits) for line in text.split('\n'))
    card = re.fullmatch(r'(Ace|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Jack|Queen|King) of (Diamonds|Hearts|Spades|Clubs)', text)
    if card:
        rank = 'Cavallo' if italian_suits and card[1] == 'Queen' else RANKS[card[1]]
        return f'{rank} di {suits[card[2]]}'
    for pattern, template in TEMPLATES:
        match = re.fullmatch(pattern, text)
        if match:
            return template.format(*(translate(v, language, italian_suits) for v in match.groups()))
    if ', ' in text:
        return ', '.join(translate(part, language, italian_suits) for part in text.split(', '))
    if '. ' in text:
        parts = text.split('. ')
        return ' '.join(translate(part + ('.' if i < len(parts)-1 else ''), language, italian_suits)
                        for i, part in enumerate(parts))
    return text


class Canvas(tk.Canvas):
    """Translate at the presentation boundary; records retain their raw values."""
    def __init__(self, *args, translator=None, **kwargs):
        self.translator = translator or (lambda text: text)
        super().__init__(*args, **kwargs)

    def create_text(self, *args, **kwargs):
        if 'text' in kwargs and not kwargs.pop('literal', False):
            kwargs['text'] = self.translator(kwargs['text'])
        return super().create_text(*args, **kwargs)

IT.update({
    'Game': 'Gioco', 'End turn': 'Termina turno', 'your pot': 'tuo pozzetto',
    'their pot': 'pozzetto avversario', 'pot taken': 'pozzetto preso',
    'pot waiting': 'pozzetto da prendere', 'your pile': 'le tue prese',
    'their pile': 'prese avversarie', 'you drew': 'hai pescato', 'they drew': 'ha pescato',
    'You declared nothing': 'Nessuna accusa', 'The computer is thinking.': 'Il computer sta pensando.',
    'The hand is over.': 'La mano è terminata.',
    'Click a card to play it, or 1 / 2 / 3.': 'Clicca una carta oppure premi 1 / 2 / 3.',
    'you vs. the computer  -  one hand': 'tu contro il computer · mano singola',
    'you vs. the computer  -  one deal': 'tu contro il computer · mano singola',
    'click or space to carry on': 'clic o spazio per continuare',
    'keys: 1 2 3 play - N new - M menu - S stats - D difficulty': '1 2 3 gioca · N nuova · M menu · S statistiche · D difficoltà',
    'keys: 1-9 and 0 play - N new - M menu - S stats': '1–9 e 0 gioca · N nuova · M menu · S statistiche',
    'click cards to pick them - H hide the hand - N new hand - M menu - S stats': 'clic seleziona · H nascondi mano · N nuova · M menu · S statistiche',
    'Pick the cards to add first.': 'Seleziona prima le carte da aggiungere.',
    'You end the turn with an empty hand': 'Termini il turno con la mano vuota',
    'someone closed the hand': 'un giocatore ha chiuso', 'the stock ran out': 'il mazzo è terminato',
    'you are ahead': 'sei in vantaggio', 'the computer is ahead': 'il computer è in vantaggio',
    'level': 'parità', 'set': 'gruppo', 'run': 'scala',
    'draws a card': 'pesca una carta', 'takes the pile': 'raccoglie gli scarti',
    'ends with an empty hand': 'termina con la mano vuota',
    'empties the hand and takes the pot': 'finisce la mano e prende il pozzetto',
    'cannot draw: the stock is out': 'non può pescare: mazzo esaurito',
    "Press 'New game' to play again.": 'Premi «Nuova partita» per giocare ancora.',
    'aces': 'assi', 'twos': 'due', 'threes': 'tre', 'three': 'tre', 'four': 'quattro',
})
TEMPLATES[:0] = [
    (r'match to (\d+)  -  (?:hand|deal) (\d+)', 'partita a {0} · mano {1}'),
    (r'match (-?\d+)', 'totale {0}'),
    (r'(\d+) in stock', '{0} nel mazzo'), (r'(\d+) in the pile', '{0} negli scarti'),
    (r'COMPUTER  (\d+) cards', 'COMPUTER · {0} carte'),
    (r'YOU  (\d+) cards', 'TU · {0} carte'),
    (r'Cards to draw: (\d+)', 'Carte da pescare: {0}'),
    (r'Cards still to deal: (\d+)', 'Carte da distribuire: {0}'),
    (r'Tricks: (\d+)/(\d+)   Still in play: (\d+)', 'Prese: {0}/{1} · Punti in gioco: {2}'),
    (r'Tricks: (\d+)   Still to win: (\d+)', 'Prese: {0} · Punti mancanti: {1}'),
    (r'Tricks: (.+)', 'Prese: {0}'),
    (r'(\d+) thirds  \+(\d+) declared', '{0} terzi · +{1} di accuse'),
    (r'(\d+) thirds', '{0} terzi'),
    (r'You declared: (.+)', 'Hai dichiarato: {0}'),
    (r'napoletana in (.+)', 'napoletana di {0}'),
    (r'(three|four) (aces|twos|threes)', '{0} {1}'),
    (r'you have to follow (.+)', 'devi rispondere a {0}'),
    (r'(Diamonds|Hearts|Spades|Clubs) - (.+)', '{0} - {1}'),
    (r'(Diamonds|Hearts|Spades|Clubs) \(drawn\)', '{0} (pescata)'),
    (r'Difficulty set to (.+) - it applies from the next move on\.', 'Difficoltà: {0}, dalla prossima mossa.'),
    (r'Selected: (\d+) card\(s\)', 'Selezionate: {0} carte'),
    (r'(\d+) cards are hidden   -   H, or the button, brings them back', '{0} carte nascoste · H o il pulsante per mostrarle'),
    (r'cards (\d+)-(\d+) of (\d+)   -   drag the wheel or the arrows', 'carte {0}–{1} di {2} · scorri con rotella o frecce'),
    (r'(\d+) burraco\(s\) - (.+)', '{0} burraco · {1}'),
    (r'You draw (.+)', 'Peschi {0}'),
    (r'You take the pile \((\d+) cards\)', 'Raccogli gli scarti ({0} carte)'),
    (r'You lay down a (set|run) of (\d+)', 'Cali una combinazione ({0}) di {1} carte'),
    (r'You add (\d+) card\(s\) to a (set|run)', 'Aggiungi {0} carte alla combinazione ({1})'),
    (r'You put the (.+) in and take the (.+)', 'Inserisci {0} e recuperi {1}'),
    (r'No meld of yours is standing on a wild card that the (.+) could replace\.', 'Nessuna tua combinazione contiene una matta sostituibile con {0}.'),
    (r'Computer (.+)', 'Il computer: {0}'),
    (r'takes the pile \((\d+) cards\)', 'raccoglie gli scarti ({0} carte)'),
    (r'lays down (\d+) cards', 'cala {0} carte'),
    (r'discards (.+)', 'scarta {0}'),
    (r'The (.+) can take in (\d+) ways: click the cards you want, then play it again\.', '{0} può prendere in {1} modi: seleziona le carte e gioca di nuovo.'),
    (r'(\d+) picked: now play the card that takes them\.', '{0} selezionate: gioca la carta che le prende.'),
    (r'The (.+) cannot take those cards\. (.+)', '{0} non può prendere queste carte. {1}'),
    (r'You take the (.+) left on the table', 'Prendi le {0} rimaste sul tavolo'),
    (r'The computer takes the (.+) left over', 'Il computer prende le {0} rimaste'),
    (r'New deal of Tressette\. (you lead|the computer leads)\.(.*)', 'Nuova mano di Tressette. {0}.{1}'),
    (r'(You|The computer) declared (.+)', '{0}: accusa {1}'),
    (r'This hand: (-?\d+) to (-?\d+), because (.+)\.', 'Questa mano: {0} a {1}, perché {2}.'),
    (r'This hand: (-?\d+) to (-?\d+)\.', 'Questa mano: {0} a {1}.'),
    (r'This deal: (\d+) to (\d+), on (\d+) thirds against (\d+)\.', 'Questa mano: {0} a {1}, con {2} terzi contro {3}.'),
    (r'Match after (\d+) hands?: (-?\d+) to (-?\d+)\.', 'Partita dopo {0} mani: {1} a {2}.'),
    (r'Playing to (\d+): (.+), and you need (\d+) more\.', 'Obiettivo {0}: {1}. Ti mancano {2} punti.'),
    (r'Declared: you (\d+), the computer (\d+)\.', 'Accuse: tu {0}, computer {1}.'),
    (r'Streak: (.+)', 'Serie: {0}'),
    (r'Saved to (.+)', 'Salvato in {0}'),
    (r'Something went wrong: (.+)', 'Si è verificato un errore: {0}'),
]
IT.update(RANKS)

IT.update({'discard\npile': 'monte\nscarti', 'trump\ndrawn': 'briscola\npescata'})
TEMPLATES[:0] = [
    (r'(\d+) coins?', '{0} denari'),
    (r'You play (.+)', 'Giochi {0}'),
    (r'The computer plays (.+)', 'Il computer gioca {0}'),
    (r'You take (.+) with (.+)', 'Prendi {0} con {1}'),
    (r'The computer takes (.+) with (.+)', 'Il computer prende {0} con {1}'),
    (r'(.+) - SCOPA', '{0} - SCOPA'),
]

IT.update({
    'the game is over': 'la partita è terminata',
    'the hand is over': 'la mano è terminata',
    'the current trick must be resolved first': 'prima bisogna assegnare la presa corrente',
    'no such card in your hand': 'questa carta non è nella tua mano',
    'the trick is incomplete': 'la presa è incompleta',
    'these cards are neither a set nor a run': 'queste carte non formano un gruppo né una scala',
    'you have already drawn this turn': 'hai già pescato in questo turno',
    'the stock is empty': 'il mazzo è vuoto',
    'the discard pile is empty': 'il monte scarti è vuoto',
    'that meld belongs to the other player': 'questa combinazione appartiene all’avversario',
    'that card is not what the wild stands for': 'questa carta non corrisponde al valore della matta',
    'discard before ending your turn': 'scarta prima di terminare il turno',
    'draw before melding or discarding': 'pesca prima di calare o scartare',
    'those cards are not all in your hand': 'non hai tutte queste carte in mano',
})
for source, target in list(IT.items()):
    if source and source[0].islower():
        IT.setdefault(source[0].upper() + source[1:] + '.', target[0].upper() + target[1:] + '.')
TEMPLATES[:0] = [
    (r'Not a meld: (.+)', 'Combinazione non valida: {0}'),
    (r'[Yy]ou have to follow suit: play (.+?)\.?', 'Devi rispondere al seme: gioca {0}.'),
    (r'a meld needs at least (\d+) cards', 'una combinazione richiede almeno {0} carte'),
    (r'it is not player (\d+)\x27s turn', 'non è il turno del giocatore {0}'),
    (r'(.+) cannot take those cards', '{0} non può prendere queste carte'),
    (r'(.+) has to take: it matches the table', '{0} deve prendere la carta dello stesso valore sul tavolo'),
    (r'lays down a (set|run) of (\d+)', 'cala una combinazione ({0}) di {1} carte'),
    (r'adds (.+) to a (set|run)', 'aggiunge {0} a una combinazione ({1})'),
    (r'puts the (.+) back and frees the (.+)', 'inserisce {0} e recupera {1}'),
]

IT.update({'Training': 'Allenamento', 'and the matching .txt': 'e nel relativo file .txt'})
