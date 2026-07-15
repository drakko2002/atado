#!/usr/bin/env python3
"""Gera src/atado/wordlist_pt.txt — lista de palavras PT-BR frequentes (E7).

Proveniência (license-safe): esta lista é GERADA por este script a partir de listas
curadas de alta frequência + regras morfológicas simples. NÃO deriva de nenhum corpus
proprietário nem do conteúdo de reuniões dos usuários (evita vazar nomes de participantes).

Uso: python scripts/build_wordlist.py
Objetivo: que `atado suspects` só sinalize siglas/nomes de verdade, e que o passe de
correção não confunda palavras comuns. Foco: reuniões institucionais (FAI/UFSCar e geral).
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

# --- função/gramática -------------------------------------------------------
FUNCTION = """
a o as os um uma uns umas de do da dos das em no na nos nas por pra para pelo pela
pelos pelas com sem sob sobre entre até após ante desde perante contra e ou mas porém
contudo todavia entretanto porque pois portanto logo então que se como quando onde
quanto qual quais quem cujo cuja cujos cujas ao aos à às num numa nuns numas dum duma
deste desta destes destas desse dessa desses dessas daquele daquela daqueles daquelas
neste nesta nestes nestas nesse nessa nesses nessas naquele naquela naqueles naquelas
isto isso aquilo este esta estes estas esse essa esses essas aquele aquela aqueles
aquelas eu tu você vocês ele ela eles elas nós vós me te se lhe nos vos lhes meu minha
meus minhas teu tua seu sua seus suas nosso nossa nossos nossas dele dela deles delas
mesmo mesma mesmos mesmas próprio própria outro outra outros outras algum alguma alguns
algumas nenhum nenhuma nenhand todo toda todos todas cada qualquer quaisquer tudo nada
algo alguém ninguém tanto tanta tantos tantas
"""

ADVERBS = """
não sim também só apenas já ainda sempre nunca jamais aqui ali lá cá acolá aí então
assim agora depois antes hoje ontem amanhã cedo tarde logo bem mal muito pouco mais
menos demais bastante quase talvez certamente realmente exatamente principalmente
justamente inclusive aliás enfim afinal ademais igualmente sobretudo geralmente
normalmente basicamente praticamente rapidamente facilmente diretamente automaticamente
manualmente localmente publicamente onde como quando porque assim melhor pior perto
longe dentro fora acima abaixo adiante atrás junto separadamente
"""

# --- verbos: formas comuns (curadas p/ os mais frequentes) ------------------
VERB_FORMS = """
ser sou é somos são era eram foi foram fui será serão seria sido sendo seja sejam fosse
estar estou está estamos estão estava estavam esteve estiveram estará estarão estaria
estado estando esteja estejam tem tenho temos têm tinha tinham teve tiveram terá terão
teria tido tendo tenha tenham haver há havia houve houveram haverá haveria havido havendo
fazer faço faz fazemos fazem fazia faziam fez fizeram fará farão faria feito fazendo faça
façam ir vou vai vamos vão ia iam foi foram irá irão iria indo vá vão vir venho vem vimos
vêm vinha vinham veio vieram virá virão viria vindo venha venham poder posso pode podemos
podem podia podiam pôde puderam poderá poderão poderia podido podendo possa possam dever
devo deve devemos devem devia deviam deveria devido devendo querer quero quer queremos
querem queria queriam quis quiseram quererá quereria querido querendo queira saber sei
sabe sabemos sabem sabia sabiam soube souberam saberá saberia sabido sabendo saiba ver
vejo vê vemos veem via viam viu viram verá veria visto vendo veja vejam dar dou dá damos
dão dava davam deu deram dará daria dado dando dê deem dizer digo diz dizemos dizem dizia
diziam disse disseram dirá diria dito dizendo diga falar falo fala falamos falam falava
falavam falou falaram falará falaria falado falando fale ficar fico fica ficamos ficam
ficava ficou ficaram ficará ficaria ficado ficando passar passo passa passamos passam
passava passou passaram passará passado passando colocar coloco coloca colocamos colocam
colocava colocou colocaram colocado colocando trabalhar trabalho trabalha trabalhamos
trabalham trabalhava trabalhou trabalharam trabalhado trabalhando precisar preciso precisa
precisamos precisam precisava precisou precisaram precisado precisando conseguir consigo
consegue conseguimos conseguem conseguia conseguiu conseguiram conseguido conseguindo
começar começo começa começamos começam começava começou começaram começado começando
chegar chego chega chegamos chegam chegava chegou chegaram chegado chegando achar acho
acha achamos acham achava achou acharam achado achando pensar penso pensa pensamos pensam
pensava pensou pensaram pensado pensando entender entendo entende entendemos entendem
entendia entendeu entenderam entendido entendendo usar uso usa usamos usam usava usou
usaram usado usando criar crio cria criamos criam criava criou criaram criado criando
buscar busco busca buscamos buscam buscava buscou buscaram buscado buscando mostrar mostro
mostra mostramos mostram mostrava mostrou mostraram mostrado mostrando apresentar apresento
apresenta apresentamos apresentam apresentou apresentado apresentando resolver resolvo
resolve resolvemos resolvem resolvia resolveu resolveram resolvido resolvendo gerar gero
gera geramos geram gerava gerou geraram gerado gerando gerenciar gerencio gerencia
gerenciamos gerenciam gerenciava gerenciou gerenciado gerenciando integrar integro integra
integramos integram integrava integrou integraram integrado integrando participar participo
participa participamos participam participou participado participando discutir discuto
discute discutimos discutem discutia discutiu discutido discutindo funcionar funciona
funcionam funcionava funcionou funcionado funcionando existir existe existem existia
existiu existido existindo receber recebo recebe recebemos recebem recebia recebeu
receberam recebido recebendo enviar envio envia enviamos enviam enviou enviaram enviado
enviando salvar salvo salva salvamos salvam salvou salvaram salvado salvando acessar
acesso acessa acessamos acessam acessou acessado acessando organizar organizo organiza
organizamos organizam organizou organizado organizando desenvolver desenvolvo desenvolve
desenvolvemos desenvolvem desenvolveu desenvolvido desenvolvendo identificar identifico
identifica identificamos identificam identificou identificado identificando permitir
permito permite permitimos permitem permitiu permitido permitindo utilizar utilizo utiliza
utilizamos utilizam utilizou utilizado utilizando cadastrar cadastro cadastra cadastramos
cadastram cadastrou cadastrado disponibilizar disponibiliza disponibilizamos comentar
comento comenta comentamos comentam comentou comentado avançar avanço avança avançamos
avançar responder respondo responde respondemos respondem respondeu respondido lembrar
lembro lembra lembramos considerar considero considera consideramos consideram considerado
perceber percebo percebe percebemos percebem percebia percebeu perceberam percebido percebendo
marcar marco marca marcamos marcam marcou marcado marcando reunir reúno reúne reunimos reúnem
reuniu reunido reunindo aprovar aprovo aprova aprovamos aprovam aprovou aprovado aprovando
"""

# --- substantivos (singular; geramos plural) --------------------------------
NOUNS = """
reunião sistema dado projeto plataforma ferramenta informação processo gestão pesquisa
ensino extensão inovação universidade instituto secretaria edital currículo laboratório
evento patente servidor pessoa gente tempo ano mês dia hora semana coisa parte forma
ponto área grupo equipe empresa acordo parceria contrato documento arquivo pasta tela
botão link site email mensagem conversa reunir ata pauta assunto tema tópico ideia questão
problema solução resultado objetivo meta prazo etapa fase versão relatório planilha
tabela lista item campo coluna linha registro banco código imagem vídeo áudio nome número
valor custo recurso orçamento verba fomento agência ministério governo público comunidade
sociedade instituição órgão setor departamento coordenação reitoria pró-reitoria campus
unidade diretoria conselho comitê membro participante coordenador diretor professor aluno
estudante técnico pesquisador docente discente cargo função papel responsabilidade demanda
serviço produto tecnologia software hardware infraestrutura rede internet navegador senha
usuário conta perfil permissão segurança privacidade licença ambiente incubadora parque
mentor mentoria consultoria protótipo empreendedor startup negócio mercado cliente proposta
programa curso disciplina graduação pós-graduação mestrado doutorado dissertação tese
artigo publicação produção citação repositório diretório busca consulta cruzamento
integração sincronização exportação importação download upload movimento início meio fim
final começo semana mês reunião encontro decisão encaminhamento pendência prazo momento
questão dúvida pergunta resposta exemplo caso vez lugar mundo história trajetória
"""

ADJECTIVES = """
bom novo velho grande pequeno alto baixo público privado institucional federal estadual
municipal técnico científico acadêmico importante possível necessário disponível próprio
principal geral específico único vários outro certo errado claro simples complexo fácil
difícil rápido lento inteiro completo parcial atual antigo recente inicial final único
digital físico virtual local nacional interno externo interessante bonito ruim melhor pior
"""

# --- números / calendário / diversos ----------------------------------------
NUMBERS = """
zero um dois três quatro cinco seis sete oito nove dez onze doze treze quatorze catorze
quinze dezesseis dezessete dezoito dezenove vinte trinta quarenta cinquenta sessenta
setenta oitenta noventa cem cento duzentos trezentos quatrocentos quinhentos mil milhão
milhões bilhão primeiro segundo terceiro quarto quinto sexto sétimo oitavo nono décimo
"""
CALENDAR = """
janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro
segunda terça quarta quinta sexta sábado domingo hoje ontem amanhã manhã tarde noite
"""
MISC = """
ok tá então né aí uai poxa olá oi tchau obrigado obrigada por favor desculpa
"""


def deaccent(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def plural(word: str) -> list[str]:
    """Plural aproximado do PT (cobertura, não perfeição)."""
    out = [word]
    if word.endswith(("a", "e", "o", "i", "u", "á", "é", "ó")):
        out.append(word + "s")
    elif word.endswith("ão"):
        out += [word[:-2] + "ões", word[:-2] + "ãos", word[:-1] + "s"]
    elif word.endswith(("r", "z", "s")):
        out.append(word + "es")
    elif word.endswith("m"):
        out.append(word[:-1] + "ns")
    elif word.endswith("l"):
        out.append(word[:-1] + "is")
    else:
        out.append(word + "s")
    return out


def fem(word: str) -> list[str]:
    out = [word]
    if word.endswith("o"):
        out.append(word[:-1] + "a")
    return out


def main() -> None:
    words: set[str] = set()

    def add(block: str, transform=None):
        for tok in block.split():
            tok = tok.strip().lower()
            if not tok or tok == "nenhand":  # guarda contra typo acidental
                continue
            forms = [tok]
            if transform:
                forms = transform(tok)
            for f in forms:
                words.add(f)
                words.add(deaccent(f))

    add(FUNCTION)
    add(ADVERBS)
    add(VERB_FORMS)
    add(NUMBERS)
    add(CALENDAR)
    add(MISC)
    add(NOUNS, plural)
    for adj in ADJECTIVES.split():
        for f1 in fem(adj.lower()):
            for f2 in plural(f1):
                words.add(f2); words.add(deaccent(f2))

    words = {w for w in words if len(w) >= 1 and w.isalpha()}
    ordered = sorted(words)

    out_path = Path(__file__).resolve().parent.parent / "src" / "atado" / "wordlist_pt.txt"
    header = (
        "# wordlist_pt — palavras PT-BR frequentes (E7). GERADA por scripts/build_wordlist.py.\n"
        "# Proveniência: listas curadas + regras morfológicas simples (MIT-safe). NÃO deriva\n"
        "# de corpus proprietário nem do conteúdo de reuniões dos usuários.\n"
        "# Uso: gate do passe de correção (§6.4) e de `suspects` (§8.1). Lookup normaliza\n"
        "# (casefold + sem-acento) — acentos aqui são irrelevantes. 1 palavra por linha.\n"
        f"# Total: {len(ordered)} palavras.\n"
    )
    out_path.write_text(header + "\n".join(ordered) + "\n", encoding="utf-8")
    print(f"{len(ordered)} palavras -> {out_path}")


if __name__ == "__main__":
    main()
