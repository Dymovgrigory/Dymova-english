# Schema.org JSON-LD snippets for Tilda

These files are ready to paste into Tilda page settings → **HTML-код для вставки внутрь HEAD**
(or a T123 block in `<head>` if you maintain the page code manually).

## What goes where

- `org_localbusiness.html` — sitewide, on every public page HEAD.
- `course_reading.html` — page `/reading` (`pageid 151292376`).
- `course_grammar.html` — page `/grammar` (`pageid 151292406`).
- `course_preparation.html` — page `/preparation` (`pageid 151292476`).
- `course_letnyaya-akademiya.html` — page `/letnyaya-akademiya` (`pageid 151229566`).
- `faq.html` — homepage (`/`, `pageid 151210576`).
- `breadcrumb_doshkolniki.html` — page `/doshkolniki` (`pageid 151228606`).
- `breadcrumb_mladshie-shkolniki.html` — page `/mladshie-shkolniki` (`pageid 151228676`).
- `breadcrumb_podrostki.html` — page `/podrostki` (`pageid 151228746`).
- `breadcrumb_reading.html` — page `/reading` (`pageid 151292376`).
- `breadcrumb_grammar.html` — page `/grammar` (`pageid 151292406`).
- `breadcrumb_preparation.html` — page `/preparation` (`pageid 151292476`).
- `breadcrumb_online-zanyatiya.html` — page `/online-zanyatiya` (`pageid 151229606`).
- `breadcrumb_podderzhivayushchie-online.html` — page `/podderzhivayushchie-online` (`pageid 151229676`).
- `breadcrumb_standartnye-offline.html` — page `/standartnye-offline` (`pageid 151229756`).
- `breadcrumb_letnyaya-akademiya.html` — page `/letnyaya-akademiya` (`pageid 151229566`).
- `breadcrumb_kontakty.html` — page `/kontakty` (`pageid 151228006`).
- `breadcrumb_novosti.html` — page `/novosti` (`pageid 151324806`).
- `breadcrumb_vakansii.html` — page `/vakansii` (`pageid 151324866`).

## Breadcrumb pattern

Use the same two-level structure everywhere on internal pages:

`Главная → <Раздел>`

## Notes

- Keep the snippets minimal and valid JSON-LD.
- Do not paste tracking scripts or Tilda form code into these files.
- The root organization graph should be reused unchanged sitewide.
