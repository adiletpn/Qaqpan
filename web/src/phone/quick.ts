import type { Lang } from '../api'

// questions people really ask: shown in the chat and as shortcuts on the home screen
export const QUICK: Record<Lang, string[]> = {
  ru: ['Мне звонят из банка — это правда?', 'Продавец на OLX просит предоплату', 'Пришло SMS про ЭЦП со ссылкой', 'Меня обманули, что делать?'],
  kk: ['Маған банктен қоңырау шалып тұр — рас па?', 'OLX-та сатушы алдын ала төлем сұрайды', 'ЭЦҚ туралы сілтемесі бар SMS келді', 'Мені алдады, не істеймін?'],
}
