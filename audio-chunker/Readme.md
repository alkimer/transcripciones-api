## 📝 Descripción

Este script hace lo siguiente:

1. **Descarga** el audio de un video de YouTube en formato MP3.  
2. **Carga** el archivo de audio en memoria usando `pydub`.  
3. **Divide** el audio en fragmentos de X segundos (configurable).  
4. **Exporta** cada fragmento como un archivo MP3 local.  
5. **Encola** un mensaje JSON en Redis por cada fragmento, con metadatos para su posterior transcripción.

Es ideal si quieres paralelizar la transcripción de videos largos, procesando cada trozo de audio de forma independiente.
