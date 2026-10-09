-- PDF rendering of the study's README.md: links into the repository lead
-- nowhere in a PDF, so they become plain text; figures fill the text width.
function Link(link)
  if not link.target:match('^https?://') then
    return link.content
  end
end

function Image(image)
  image.attributes.width = '100%'
  return image
end

-- The italic paragraph under each figure is its caption; drop the one
-- Pandoc makes from the image's alt text.
function Figure(figure)
  return figure.content
end
