-- Keep explicit PDF page divisions invisible in normal Markdown rendering.
function RawBlock(block)
  if block.format == 'html' and block.text:match('^<!%-%- pagebreak %-%->$') then
    if FORMAT == 'typst' then
      return pandoc.RawBlock('typst', '#pagebreak()')
    end
    return {}
  end
end

-- Use the companion vector figure in PDF while retaining PNGs for Markdown.
function Image(image)
  if FORMAT == 'typst' then
    image.src = image.src:gsub('%.png$', '.svg')
    return image
  end
end
